# Changelog

All notable changes to PyPhotoOrganizer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-01-02

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

### In Progress

- None currently

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

*Last updated: 2026-01-02*
