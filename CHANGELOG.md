# Changelog

All notable changes to PyPhotoOrganizer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2026-01-12

### Changed - UI Reorganization

**Three-Tab Settings Structure:**
Reorganized settings into three focused top-level tabs for better usability and discoverability:

**📥 Import Settings Tab** (NEW - replaces Sources tab):
- Source folders management (add/remove, enable/disable checkboxes)
- Ignored directories configuration with wildcard patterns
- File processing settings (subdirectories, batch size)
- Photo filtering settings (dimensions, file size, EXIF requirements)
- Filename pattern filtering (exclude icons, thumbs, etc.)
- **Start/Stop processing buttons** (moved from Sources tab)

**📦 Archive Settings Tab** (NEW - extracted from Settings tab):
- Archive location display (read-only from database)
- Organization template configuration (presets + custom with live preview)
- File type organization (combined/subfolder/separate for videos)
- File renaming settings (enable checkbox, template editor, live preview)

**⚙️ System Settings Tab** (NEW - combines Database + Settings tab features):
- Database information and statistics (from old Database tab)
- Operation mode selection (Copy vs Move)
- Performance settings (partial hash configuration)
- Thumbnail cache settings (memory size, worker threads)
- Import history retention (mode, count, cleanup)
- Settings file management (Load/Save/Restore/Validate)

**Benefits:**
- Clearer workflow: Import → Archive → System
- Related settings grouped logically
- Better discoverability - settings are where users expect them
- Eliminated redundancy from Database/Sources/Settings tabs
- Consistent naming with clear icons

**Files Modified:**
- `ui/main_window.py` - Updated to use new three-tab structure
- `ui/import_settings_tab.py` - NEW (~850 lines)
- `ui/archive_settings_tab.py` - NEW (~900 lines)
- `ui/system_settings_tab.py` - NEW (~700 lines)

**Deprecated:**
- `ui/setup_tab.py` - Replaced by import_settings_tab.py
- `ui/settings_tab.py` - Split into archive_settings_tab.py and system_settings_tab.py
- `ui/database_tab.py` - Merged into system_settings_tab.py

**Documentation Updated:**
- CLAUDE.md - GUI Modules section updated
- README.md - Processing workflow and tab descriptions updated
- QUICKREF.md - Workflow and tab quick reference updated
- ARCHITECTURE.md - UI file structure updated

---

## [2.3.1] - 2026-01-06

### Added - Database Reliability Improvements

**WAL Mode and Timeout Handling:**
- All database connections now use WAL (Write-Ahead Logging) mode
- 30-second connection timeouts prevent "database is locked" errors
- Retry logic with exponential backoff for audit logging
- Better concurrent access support for main processing + audit logging

**Log Rotation:**
- Automatic log rotation at 5MB file size
- Keeps 3 backup files (total ~20MB max per module)
- Prevents unbounded log growth during long-running operations
- Uses Python's RotatingFileHandler

**Files Modified:**
- `DuplicateFileDetection.py` - WAL mode in PhotoDatabase class
- `database_metadata.py` - WAL mode in _get_connection()
- `audit_manager.py` - WAL mode + retry logic for log_file_operation()
- `utils.py` - RotatingFileHandler in setup_logger()

---

## [2.3.0] - 2026-01-05

### Added - Import Audit System

**Complete Audit Trail:**
- New `ImportSession` table tracks each processing run
- New `FileProcessingLog` table logs every file operation
- New `DuplicateMapping` table tracks original-duplicate relationships
- New `AuditRetentionSettings` table for cleanup configuration

**Import History Tab (New):**
- Session dropdown with status filtering (completed, failed, cancelled)
- Statistics dashboard (scanned, processed, new, duplicates, filtered, errors)
- File operations grid with 8 columns (sortable, resizable)
- Custom QAbstractTableModel for 100k+ record performance
- Image preview panel with rubber band zoom
- File details panel with EXIF metadata display
- Export buttons: JSON, CSV, Duplicates CSV
- Delete session functionality

**audit_manager.py (New Module):**
- `AuditManager` class for session lifecycle management
- `start_session()`, `end_session()`, `get_session()` methods
- `log_file_operation()` with retry logic for concurrent access
- `record_duplicate()` for tracking duplicate relationships
- `generate_session_report()`, `generate_duplicate_report()`, `generate_error_report()`
- `export_session_to_json()`, `export_session_to_csv()`, `export_duplicates_to_csv()`
- Retention management: `get_retention_settings()`, `set_retention_settings()`, `apply_retention_policy()`

**Integration Points:**
- worker.py: Session lifecycle management
- DuplicateFileDetection.py: Logs duplicates and filtered files
- main.py: Logs copy/move operations with error tracking

**Files Added:**
- `audit_manager.py` - Core audit infrastructure
- `ui/import_history_tab.py` - Import History tab UI

**Files Modified:**
- `ui/main_window.py` - Added Import History tab
- `ui/worker.py` - Session start/end integration
- `DuplicateFileDetection.py` - Duplicate and filter logging
- `main.py` - Copy/move operation logging

---

## [2.2.3] - 2026-01-05

### Added - Hash History System

**Purpose:** Preserve duplicate detection capability after EXIF modifications.

**Problem Solved:**
- When date corrections are written to image EXIF data, the file hash changes
- Without hash history, the same original file would be copied again as "new"
- Hash history maintains all historical hashes for each photo

**Database Schema:**
- New `FileHashHistory` table with current_file_hash, historical_hash, created_date, reason
- Index on historical_hash for fast duplicate detection lookups
- Reasons: 'original', 'migration', 'exif_edit', 'date_correction'

**Key Methods (DuplicateFileDetection.py):**
- `is_duplicate_hash_in_history(hash)` - Check historical records
- `get_all_historical_hashes()` - Load all for batch checking
- `add_hash_to_history(old_hash, new_hash, reason)` - Record changes
- `get_photo_by_historical_hash(hash)` - Find photo by any historical hash

**Key Methods (exif_writer.py):**
- `update_file_hash_after_modification()` - Recalculate and update after EXIF write

**Integration:**
- date_correction_dialog.py calls hash update after EXIF write
- find_duplicates() checks both current and historical hashes
- Automatic migration adds existing records with reason='migration'

### Fixed

**EXIF Extraction Platform Bug:**
- Fixed: EXIF was only extracted on Windows, causing all Linux/macOS files to be flagged as unreliable
- Now platform-independent EXIF extraction works on all operating systems
- Location: DuplicateFileDetection.py lines 419-536

**Case-Insensitive Extensions:**
- File extension comparison now case-insensitive
- Handles .JPG, .jpg, .Jpg identically

---

## [2.2.2] - 2026-01-04

### Added - File Renaming System

**Template-Based Renaming:**
- New `filename_template.py` module for template parsing and validation
- Template variables: {year}, {month}, {day}, {hour}, {minute}, {second}
- Original filename: {original_name}, {original_name_no_ext}, {ext}
- Folder names: {folder_name}, {parent_folder_name}
- Sequential counter: {counter} or {counter:04d} (zero-padded)

**Settings Tab Integration:**
- Enable/disable checkbox for file renaming
- Template input with live preview
- Validation feedback for invalid templates
- Per-database template storage

**Database Schema:**
- Added `enable_file_rename` column to DatabaseMetadata
- Added `filename_template` column to DatabaseMetadata
- New `FileRenameHistory` table tracks original → renamed mappings

**Security Features:**
- Path traversal prevention (blocks .., /, \)
- Dangerous character blocking (<, >, :, ", |, ?, *)
- Template validation before saving
- Fallback to {original_name} on parse errors

**Collision Handling:**
- Automatic counter suffix (_1, _2, _3) for filename conflicts
- No user intervention required

### Fixed

**Critical Bug:**
- Fixed `get_metadata()` not including `enable_file_rename` and `filename_template` columns
- This caused `is_file_rename_enabled()` to always return False

**Logging:**
- Changed logging from DEBUG to INFO for better visibility

**Files Modified:**
- `database_metadata.py` - Added file rename columns and methods
- `ui/settings_tab.py` - Added file renaming UI section
- `main.py` - Integrated file renaming during processing
- `utils.py` - Enhanced get_unique_filename() for collision handling

**Files Added:**
- `filename_template.py` - Template parsing and validation

---

## [2.2.1] - 2026-01-04

### Added - Grid Interaction Improvements

**Read-Only Table Cells:**
- All table cells (except checkboxes) are read-only
- Prevents accidental data editing in grids

**Extended Selection Mode:**
- Shift+Click: Select range of rows
- Ctrl+Click: Toggle individual row selection
- Checkboxes auto-sync with row selection
- Double-click row to toggle checkbox

**Checkbox Column Support:**
- Shift/Ctrl clicks work on checkbox column same as other columns
- Consistent behavior across all grids (Date Corrections, Setup, Filtered Files, Logs)

### Added - Dialog and Workflow Improvements

**Multi-Monitor Support:**
- All dialogs center on main application window
- Uses `parent.window().frameGeometry()` for correct positioning
- Works correctly in multi-monitor setups

**Batch Operations:**
- Success confirmations suppressed for batch operations
- Only error dialogs shown (allows uninterrupted workflow)
- Detailed logging still captures all operations

### Added - Enhanced Logging

**Visual Indicators:**
- ✓ - Successful operations
- ✗ - Failed operations
- ⚠ - Warnings (e.g., file collisions)
- ℹ - Informational messages

**Section Markers:**
- 80-char `=` lines for process start/end
- 60-char `-` lines for individual file processing

**Date Correction Dialog:**
- Per-file EXIF write tracking
- Separate error lists: exif_failures, db_failures
- Detailed summary reports

**Reorganization Worker:**
- Per-file detailed logging with hash, dates, paths
- Directory creation and collision handling tracking
- Final summary with success rate percentage

### Added - Audit Trail

**original_archive_path Column:**
- Stores file location BEFORE reorganization
- Enables verification of file movements
- Displayed in Date Corrections tab details panel

**Status Tracking:**
- Pending (Gray): No correction applied
- Corrected (Green): Date corrected, waiting for reorganization
- Reorganized (Blue): File moved to correct date folder

### Fixed

**Remove Selected Button:**
- Now works with checkbox-based selection in Setup tab

**Files Modified:**
- `ui/date_corrections_tab.py` - Grid interactions, logging, audit trail
- `ui/setup_tab.py` - Grid interactions, Remove Selected fix
- `ui/date_correction_dialog.py` - Dialog centering, enhanced logging
- `ui/reorganize_worker.py` - Detailed logging, audit trail
- `database_metadata.py` - original_archive_path column

---

## [2.2.0] - 2026-01-03

### Added - Date Correction System

**Automatic Detection:**
- System flags files with unreliable dates during processing
- Detection criteria: no EXIF, year 1000 fallback, suspicious dates, user-specified paths

**Date Corrections Tab (New):**
- Sortable grid with filter by flag reason and status
- Image preview panel with rubber band zoom (click-drag to zoom, double-click to reset)
- Single file correction dialog with date picker
- Batch correction with same date or sequential dates
- Reorganize All Marked button for batch file moves

**UnreliableDates Table (New):**
- file_hash, source_path, archive_path, original_archive_path
- original_date, date_source, flag_reason
- corrected_date, correction_timestamp, needs_reorganization

**EXIF Writing:**
- New `exif_writer.py` module
- `write_exif_date()` - Writes to DateTimeOriginal, DateTime, DateTimeDigitized
- `read_exif_date()` - Reads DateTimeOriginal
- `verify_exif_write()` - Verifies write succeeded
- **IMPORTANT**: Only writes to archive files, never to source files

**Safe Reorganization:**
- Copy-verify-delete pattern prevents data loss
- Empty directory cleanup after moves
- Database path updates for both UniquePhotos and UnreliableDates

**User-Specified Paths:**
- Manage Unreliable Paths dialog
- Auto-flag files from configured paths (e.g., scanned photos folder)

**Files Added:**
- `exif_writer.py` - EXIF date writing
- `ui/date_corrections_tab.py` - Date Corrections tab
- `ui/date_correction_dialog.py` - Date input dialog
- `ui/manage_unreliable_paths_dialog.py` - Unreliable paths management
- `ui/reorganize_worker.py` - File reorganization logic

**Files Modified:**
- `database_metadata.py` - UnreliableDates table, unreliable date methods
- `DuplicateFileDetection.py` - Date reliability detection during processing
- `ui/main_window.py` - Added Date Corrections tab

---

## [2.1.0] - 2026-01-02

### Added - Persistent Source Directories

**Database-Backed Source Management:**
- New `SourceDirectories` table stores all source folder configurations
- Source directories persist across application sessions
- Each source tracks: path, enabled status, added date, last scanned timestamp
- Automatic loading when database is selected
- Auto-save when sources are added or removed

**Enhanced Source Selection UI:**
- Rich table widget with Enable Checkbox, Status Icon, Source Path, Last Scanned, Status
- Mouse-over tooltips show detailed status information
- "Refresh Status" button to re-validate all paths

**Intelligent Path Validation:**
- Real-time validation for path existence, directory type, and readability
- Special handling for network paths (GVFS mounts)
- Helpful error messages for unmounted network shares

**Database Methods:**
- `add_source_directory()`, `remove_source_directory()`, `get_all_source_directories()`
- `update_source_last_scanned()`, `update_source_enabled()`, `clear_all_source_directories()`

### Added - Window Positioning Management

**Intelligent Window Placement:**
- All windows center on screen on first launch (no more upper-left corner)
- Main window position persistence using Qt QSettings
- Automatic position restoration on application restart
- Title bar protection ensures window is always accessible (minimum 50px visible)
- Screen bounds checking on all four edges
- Dialog centering on parent window (or screen if no parent)
- Works across multi-monitor setups

**Files Modified:**
- `ui/main_window.py` - Added geometry save/restore with QSettings
- `ui/database_selector_dialog.py` - Added center_on_parent() method
- `ui/create_database_dialog.py` - Added center_on_parent() method

**Settings Storage:** `~/.config/PyPhotoOrganizer/MainWindow.conf`

### Added - Separate Photo/Video Archive (Complete Implementation)

**Database Tab - Video Archive Management:**
- New "Video Archive Location (Optional)" group box
- Enable/disable checkbox: "Store videos in separate location"
- Browse button to select video archive folder
- Set button to apply selected location
- Real-time status indicator showing folder existence
- Automatic folder creation with user confirmation
- Validation prevents same location for photos and videos
- Clear visual feedback (green checkmark, red warning, orange info)

**Create Database Dialog - Video Archive Setup:**
- Optional video archive configuration during database creation
- Checkbox: "Store videos in a separate location from photos"
- Browse button for video archive location (enabled when checkbox checked)
- Comprehensive validation:
  - Ensures paths are absolute
  - Prevents duplicate photo/video archive locations
  - Offers to create folders if they don't exist
- Automatically sets video archive in database metadata
- Success message shows both photo and video archive locations

**File Routing Logic (main.py):**
- Intelligent file type detection using `utils.is_video_file()`
- Automatic routing decisions:
  - Videos → video archive (if enabled and location set)
  - Photos → photo archive (default)
- Same date-based folder structure for both (YYYY/MM/DD)
- Clear logging of routing decisions for each file
- Seamless integration with existing processing pipeline

**Supported File Types:**
- **Photos**: `.jpg`, `.jpeg`, `.png`, `.heic`, `.heif`, `.tif`, `.tiff`, `.bmp`, `.gif`, `.webp`
- **Videos**: `.mov`, `.mp4`, `.avi`, `.mkv`, `.wmv`, `.flv`, `.mpg`, `.mpeg`, `.m4v`, `.3gp`

**Use Cases:**
- Store videos on NAS while keeping photos local
- Separate high-resolution videos to external drive
- Keep photos on SSD for fast access, videos on HDD for storage
- Maintain single database for both media types

**Files Modified:**
- `ui/database_tab.py` - Added video archive UI (+ QCheckBox import)
- `ui/create_database_dialog.py` - Added optional video archive during creation
- `main.py` - Implemented file routing logic with database metadata integration

### Improved - Splash Screen Performance & UX

**Instant Splash Screen Display:**
- Implemented deferred import pattern for immediate splash screen appearance
- Splash screen now appears in ~50-100ms (vs 2-5 second delay previously)
- Heavy module imports (MainWindow, tabs, PIL, etc.) deferred until after splash is visible
- Splash screen centers on primary monitor immediately

**Progressive Loading Messages:**
- Real-time status updates on splash screen during initialization
- Loading sequence:
  1. "Loading application..."
  2. "Loading modules..." (importing MainWindow and dependencies)
  3. "Initializing user interface..." (creating MainWindow)
  4. "Creating tabs..." (initializing all tabs)
  5. "Restoring window position..." (geometry restoration)
  6. "Loading settings..." (silent settings load)
- Database selector dialog deferred until after splash closes (non-blocking)

**Silent Settings Loading:**
- Settings load silently during startup (no blocking dialogs)
- "Settings Loaded" dialog only shown when user manually loads settings
- Added `show_dialog` parameter to `SettingsTab.load_from_file()` method

**Files Modified:**
- `main_gui.py` - Deferred import pattern, splash centering, progressive messages
- `ui/main_window.py` - Added splash_callback parameter, QTimer for deferred database selector
- `ui/settings_tab.py` - Silent loading during initialization

**User Experience:**
- Before: Black screen for 2-5 seconds, then brief splash, then "Settings Loaded" dialog
- After: Instant splash with clear progress indication, smooth transition to main window

### Added - Network Location Browsing (Similar to File Manager)

**Intelligent Network Discovery Dialog:**
- New "Browse Network..." button with automatic network host and share discovery
- **Network Host Discovery** (similar to file manager's Network view):
  - Discovers SMB/CIFS hosts on local network automatically
  - Uses avahi-browse (mDNS/Zeroconf), nmblookup (NetBIOS), and GVFS mounts
  - Shows list of discovered network computers/servers
  - Double-click host to view available shares
- **Share Listing**:
  - Automatically lists SMB shares on selected host using smbclient
  - Filters out administrative shares (ending with $)
  - Shows accessible shares without requiring manual mounting
- **Background Processing**:
  - Network discovery runs in background thread (non-blocking UI)
  - Progress indicators during discovery and share listing
- **User-Friendly Workflow**:
  1. Click "Browse Network..."
  2. Wait for network hosts to be discovered
  3. Double-click a host to see its shares
  4. Select a share and click "Select Folder"
  5. Network path (//hostname/share) added to source list
- Complements existing "Add Network Path..." manual entry option
- "Clear All" button to quickly remove all source folders

**Technical Implementation:**
- Custom NetworkBrowserDialog with QThread-based discovery
- Fallback gracefully if tools not installed (avahi, smbclient)
- Helpful error messages with installation instructions
- Cross-platform design (currently optimized for Linux)

**Use Cases:**
- Browse and select NAS folders (Synology, QNAP, FreeNAS, etc.) without pre-mounting
- Discover and access SMB/CIFS network shares from other computers
- No need to manually mount shares before adding them
- Similar workflow to file manager's Network browsing

**Files Added:**
- `ui/network_browser_dialog.py` - Network discovery dialog with background worker

**Files Modified:**
- `ui/setup_tab.py` - Updated browse_network_locations() to use network browser dialog

### Fixed

**Import Errors:**
- Added missing `QCheckBox` import to `ui/database_tab.py`

**Startup Performance:**
- Fixed splash screen not displaying until after heavy imports completed
- Fixed blocking dialogs during application initialization

**Database Statistics:**
- Fixed total photos count always showing 0 in Database Tab and Database Selector
- Added `refresh_total_photos()` method to count photos from UniquePhotos table
- Automatic count update after processing completes
- Manual refresh via "Refresh Statistics" button in Database Tab
- Count now accurately reflects number of unique photos in database

## [2.0.0] - 2026-01-02

### Added - GUI Implementation

**Major Feature: Full-Featured Graphical User Interface**
- Professional splash screen with loading status on startup
- Tab-based interface with 7 comprehensive tabs
- Background worker thread for responsive UI during processing
- Real-time progress tracking with EMA-based time estimates
- Database-first architecture with startup database selector

**Setup Tab:**
- Multi-folder source selection with Add/Remove buttons
- Archive location display (managed by database)
- Copy/Move mode radio buttons with move confirmation dialog
- Start/Stop processing with graceful stop capability

**Progress Tab:**
- Overall progress bar with files count
- Elapsed time and estimated remaining time (EMA algorithm)
- Stage-specific progress (Scanning, Processing, Organizing)
- Auto-expanding status log with color-coded messages (info, warning, error)
- Processing rate display (files/second)

**Results Tab:**
- Copyable statistics text (total examined, originals, duplicates, filtered)
- "Copy Statistics to Clipboard" button for easy sharing
- Processing time and summary information

**Filtered Files Tab (573 lines):**
- Comprehensive table showing all filtered files
- Filter reason column with user-resizable columns
- Filter by reason dropdown
- File details panel with all attributes
- Image preview (400x300 thumbnail)
- Action buttons: Open File, Open Folder, Copy Path
- Export to CSV/TXT
- Statistics summary by filter reason
- Vertical splitter between details and preview panels

**Logs Tab (571 lines):**
- Multi-log file support with dropdown selector
- Statistics dashboard with clickable filter counts by level
- Level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Real-time search across all log entries
- Time range filter (Last 5 min, hour, today, all time)
- Details panel for viewing full log entry
- Export logs to CSV/TXT
- Clear log file with confirmation
- Selection persistence during auto-refresh
- Intelligent log parsing (handles variable formats)

**Settings Tab:**
- File Processing settings (subdirectories, batch size)
- Organization settings (group by year/day with preview)
- Performance settings (partial hashing configuration)
- Photo Filtering settings (size, dimensions, square detection, EXIF)
- Filename Pattern Filtering with management UI
- Actions: Load, Save, Restore Defaults, Validate

**Database Tab:**
- View database metadata (name, description, creation date)
- Display archive location (permanently bound)
- Show statistics (total photos, last used)
- Change database functionality

### Added - Database-First Architecture

**DatabaseMetadata Management:**
- New `DatabaseMetadata` table in SQLite database
- Stores database name, description, archive location
- Creation date and last used date tracking
- Schema version for future upgrades
- Video archive location and separate_video_archive flag (partial implementation)

**Database Dialogs:**
- Database Selector Dialog (205 lines) - shown on startup
- Create Database Dialog (274 lines) - wizard for new databases
- Required database selection to proceed
- Lists all available databases with metadata
- Auto-creates archive folder if needed

**Automatic Schema Upgrades:**
- Detects and upgrades old databases automatically
- Adds missing columns (video_archive_location, separate_video_archive)
- Ensures all required tables exist (UniquePhotos, DatabaseMetadata)
- Backward compatible with existing databases

### Added - Advanced Filtering

**Filename Pattern Filtering UI:**
- Customizable list of excluded patterns
- Add/Remove patterns with duplicate detection
- Restore default patterns button with confirmation
- Enable/disable pattern filtering checkbox
- Pattern count display
- Saved to settings.json

**Enhanced Filter Statistics:**
- Detailed breakdown by filter reason
- Filtered files tracked with comprehensive metadata
- File size, dimensions, format, mode, EXIF presence
- Individual filter check results for each criterion
- Reviewable in dedicated Filtered Files tab

### Added - File Type Detection

**New Utilities:**
- `is_video_file(file_path)` - Detect video files by extension
- `is_photo_file(file_path)` - Detect photo files by extension
- Separate constants for PHOTO_EXTENSIONS and VIDEO_EXTENSIONS
- Foundation for separate photo/video archive routing

### Improved - User Experience

**Active UI Principle:**
- No disabled/grayed-out buttons
- All buttons stay enabled with informative dialogs
- Clear explanations when actions aren't available
- Better user guidance and transparency

**Resizable Interface:**
- Horizontal splitter in Filtered Files tab (table vs preview)
- Vertical splitter in Filtered Files tab (details vs preview)
- All text boxes expand with window resize
- User-resizable table columns
- Customizable panel layouts

**Immediate Feedback:**
- Splash screen shows instantly on startup
- Loading status messages during initialization
- No blank screen delays
- Professional application appearance

### Fixed - Critical Bugs

**Data Flow Issues:**
- Fixed filtered_files not appearing in UI (missing from return dictionary)
- Fixed filtering data structure - now includes comprehensive file metadata
- Fixed worker expecting filtered_files but not receiving it from main.py

**UI Rendering Issues:**
- Fixed "unknown property cursor" warnings (changed from CSS to Qt setCursor)
- Fixed Progress Tab status log not resizing vertically
- Fixed Filter Statistics text box not expanding
- Fixed File Details text box not expanding
- Fixed table columns not user-resizable in Filtered Files tab

**Selection and State:**
- Fixed log table selection lost during auto-refresh
- Added selection persistence by matching raw log line
- Disabled auto-scroll when user has row selected (reading)

**Layout Issues:**
- Added proper stretch factors to all layouts
- Fixed components not expanding to fill available space
- Corrected minimum vs maximum height settings

### Changed - Code Quality

**Constants Module:**
- Eliminated all magic numbers
- Centralized application constants
- Added PHOTO_EXTENSIONS and VIDEO_EXTENSIONS
- Improved code readability and maintainability

**Database Schema:**
- Added video_archive_location column
- Added separate_video_archive flag
- Schema version tracking for future upgrades
- Automatic column addition for old databases

**Error Handling:**
- Comprehensive try-catch in all UI methods
- Better error messages with full stack traces
- Graceful degradation when features unavailable
- Informative dialogs instead of silent failures

### Technical Debt Reduction

**Code Organization:**
- Modular UI architecture (9 UI files, ~2,500 lines)
- Separation of concerns (model-view-controller pattern)
- Reusable components (ClickableLabel, splitters)
- Consistent naming conventions

**Performance Optimizations:**
- Background worker thread prevents UI blocking
- EMA algorithm for accurate time estimates
- Efficient database queries with proper indexing
- Smart log parsing with caching

**Documentation:**
- Comprehensive inline documentation
- Updated README.md with GUI features
- Created CHANGELOG.md for version tracking
- Detailed GUI Tabs Reference section

## [1.0.0] - 2024-12-01

### Added - Initial Release

**Core Features:**
- SHA-256 based duplicate detection
- Two-stage partial hashing for large files
- Date-based organization (YYYY/MM/DD)
- HEIC to JPEG conversion with metadata preservation
- Multiple source directory support
- Resume capability with batch commits

**Photo Filtering:**
- Size-based filtering
- Dimension-based filtering
- Square icon detection
- Filename pattern exclusion
- EXIF data requirement (optional)

**Command Line Interface:**
- Progress bars with tqdm
- Real-time statistics
- Detailed logging to files
- Configuration via settings.json

**Database:**
- SQLite for hash storage
- Indexed lookups for performance
- Batch commits for long-running processes
- Resume support

**Security:**
- Path traversal protection
- SQL injection prevention
- Input validation
- File lock handling

## [Unreleased]

### Planned

**Short Term:**
- Add database backup functionality
- Archive location migration feature (move existing archives to new location)

**Medium Term:**
- Cross-platform path improvements
- Parallel processing support
- Video metadata extraction
- Undo/rollback functionality

**Long Term:**
- Cloud storage integration
- Machine learning photo quality scoring
- Dark theme for GUI
- Timeline view
- Face detection and tagging

---

## Version Numbering

- **Major version** (X.0.0): Incompatible API changes or major feature additions
- **Minor version** (0.X.0): New features in a backward-compatible manner
- **Patch version** (0.0.X): Backward-compatible bug fixes

## Links

- [Repository](https://github.com/yourusername/PyPhotoOrganizer)
- [Issue Tracker](https://github.com/yourusername/PyPhotoOrganizer/issues)
- [Documentation](README.md)

---

*Last updated: 2026-01-06*
