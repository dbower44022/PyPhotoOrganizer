# CLAUDE.md

Guidance for Claude Code when working with this repository. **For end-user docs, see [USER_GUIDE.md](USER_GUIDE.md).**

## Project Overview

PhotoOrganizer is a Python photo/video duplicate detection and organization system. It scans source directories, detects duplicates via SHA-256 hashing, and organizes unique files into a date-based archive (year/month/day).

**Primary Goal**: Consolidate photos from multiple devices into a single, deduplicated archive while preserving metadata.

## CRITICAL: Source File Protection

**SOURCE FILES MUST NEVER BE MODIFIED.**

- All source directories are read-only. Files are copied FROM sources, never written TO.
- EXIF corrections are written ONLY to archive files, never to source files.
- When implementing features: Ask "Does this modify a source file?" If yes, redesign.

## CRITICAL: UI Design Guidelines

**Controls must NEVER be grayed out or disabled.**

- All buttons always enabled and clickable
- Handle empty states with informative messages when clicked
- Use `QMessageBox.information()` if preconditions not met

## Running the Application

```bash
python main_gui.py          # Import GUI (archive setup, import management)
python photo_review_app.py  # Photo Review (browse, review, correct)
python main.py              # CLI mode
```

## Architecture

### Two Applications

**Import GUI** (`main_gui.py`): 6 tabs for import settings, archive settings, system settings, progress, import history, logs.

**Photo Review** (`photo_review_app.py`): Grid browsing, date correction, rotation, deletion, albums.

### Core Modules

| Module | Purpose |
|--------|---------|
| `main.py` | Orchestration: `organize_files()` copies/moves unique files to archive |
| `DuplicateFileDetection.py` | `PhotoDatabase`, `find_duplicates()`, `get_creation_date()`, `hash_file()`, `hash_image_content()` |
| `database_metadata.py` | `DatabaseMetadata` class: archive binding, source dirs, unreliable dates |
| `config.py` | `Config` class: settings loading with defaults |
| `photo_filter.py` | `PhotoFilter`: filters icons/thumbnails by size/dimensions/filename |
| `exif_writer.py` | `write_exif_date()`, `read_exif_date()` |
| `audit_manager.py` | `AuditManager`: session tracking, file operation logging |
| `album_manager.py` | `AlbumManager`: album CRUD, photo-to-album operations |

### GUI Modules (ui/)

| Module | Purpose |
|--------|---------|
| `main_window.py` | Main window, 6-tab interface |
| `import_settings_tab.py` | Source folders, album associations, filtering, Start/Stop buttons |
| `archive_settings_tab.py` | Organization template, file renaming |
| `system_settings_tab.py` | Database info, copy/move mode, performance |
| `progress_tab.py` | Real-time progress display |
| `import_history_tab.py` | Session history, file preview, export, override skip |
| `worker.py` | `ProcessingWorker` background thread |
| `reprocess_worker.py` | `ReprocessWorker` for reprocessing/override skip with album support |
| `content_hash_worker.py` | `ContentHashBackfillWorker` for backfilling content hashes |
| `archive_change_scanner_worker.py` | `ArchiveChangeScannerWorker` for detecting external file modifications |
| `theme.py` | `ThemeManager`, light/dark mode support |

### Database Tables

All tables in SQLite database (default: `PhotoDB.db`):

| Table | Purpose |
|-------|---------|
| `DatabaseMetadata` | Archive location, settings, schema version |
| `UniquePhotos` | File hashes, paths, creation dates, revision tracking, content_hash (Schema v5) |
| `SourceDirectories` | Persistent source folder configs with album associations |
| `SourceDirectorySubAlbums` | Tracks auto-created sub-albums for source subdirectories |
| `UnreliableDates` | Files with questionable dates |
| `FileRenameHistory` | Original→renamed filename mappings |
| `DeletedFiles` | Soft-delete tracking with restore capability |
| `FileVersions` | Revision history for rotations/edits |
| `Albums` | Album metadata |
| `AlbumPhotos` | Album-to-photo junction table |
| `ImportSession` | Audit session tracking |
| `FileProcessingLog` | Per-file operation audit log |
| `DuplicateMapping` | Original-to-duplicate relationships |

**Note (Schema v5):** The `FileHashHistory` table is no longer used. All hashes (including revision hashes) are stored directly in `UniquePhotos` with `file_hash` as the primary key. The `revised_photo` column links revisions to their parent file.

### Database Connection Pattern

All modules use WAL mode for concurrent access:
```python
conn = sqlite3.connect(path, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
```

### Database Auto-Upgrade

`DatabaseMetadata._ensure_metadata_table()` and similar methods automatically add missing columns/tables on first access using `ALTER TABLE ... ADD COLUMN`. No manual migrations needed.

## Key Implementation Details

### Processing Flow

1. `get_file_list()` scans sources for media files
2. `PhotoFilter` excludes icons/thumbnails (videos pass through)
3. `find_duplicates()` hashes files, checks against database
4. Unique files: `organize_files()` copies to archive with date-based folders
5. Database updated with hashes and paths

### Graceful Shutdown (Stop Processing)

Uses cooperative cancellation pattern:

1. User clicks "Stop" → `worker.stop()` sets `_should_stop = True`
2. `should_stop` callable passed to `organize_files()` and `find_duplicates()`
3. Processing loops check `should_stop()` at start of each file
4. On stop: commits uncommitted work, returns `was_cancelled=True`
5. UI shows accurate partial results; user can resume later

**Key implementation:**
- `ProcessingWorker.stop()`: Sets `_should_stop = True`
- `ProcessingWorker._check_should_stop()`: Callable passed to processing functions
- Progress callbacks return `True` when stop requested to signal cancellation
- `find_duplicates()` and `organize_files()` both accept `should_stop` parameter
- On cancellation, uncommitted work is committed before returning

**Resume capability**: Re-running skips already-processed files (detected as duplicates via hash).

### Dialog Worker Thread Cleanup

Dialogs that spawn QThread workers must implement `closeEvent` to prevent "QThread destroyed while thread is still running" errors and database lock issues.

**Required pattern for dialogs with workers:**
```python
from PySide6.QtGui import QCloseEvent

class MyDialog(QDialog):
    def __init__(self, ...):
        super().__init__(...)
        self.worker = None  # Initialize to None
        ...

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close - ensure worker thread is properly stopped."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()  # Request graceful stop
            self.worker.wait()    # Block until thread finishes
        event.accept()
```

**Dialogs with this pattern implemented:**

| Dialog | Worker Variable | File |
|--------|-----------------|------|
| `AddToAlbumDialog` | `self.worker` | `ui/add_to_album_dialog.py` |
| `RotateImageDialog` | `self.rotate_worker` | `ui/rotate_image_dialog.py` |
| `BatchEditDialog` | `self.batch_worker` | `ui/batch_edit_dialog.py` |
| `DeletedFilesDialog` | `self.restore_worker` | `ui/deleted_files_dialog.py` |
| `EditImageDialog` | `self.edit_worker` | `ui/edit_image_dialog.py` |

**Tab/Window worker cleanup:**

Tabs and main windows with background workers provide a `cleanup_workers()` method called from main window `closeEvent`:

| Component | Worker(s) | File |
|-----------|-----------|------|
| `MainWindow` | `self.worker` (ProcessingWorker) | `ui/main_window.py` |
| `SystemSettingsTab` | `self._backfill_worker` | `ui/system_settings_tab.py` |
| `ImportHistoryTab` | `self.reprocess_worker`, `self.override_skip_worker` | `ui/import_history_tab.py` |
| `ArchiveMaintenanceTab` | `self._backup_worker`, `self._verification_worker`, `self._storage_stats_worker`, `self._change_scanner_worker` | `ui/archive_maintenance_tab.py` |
| `PhotoReviewWindow` | `self.delete_worker` | `photo_review/review_window.py` |

Main window calls `_cleanup_tab_workers()` in `closeEvent` which calls each tab's `cleanup_workers()` method.

**Why this matters:** Without `closeEvent`, closing a dialog while a worker is running causes Qt to destroy the thread object mid-execution. This leads to database locks, corrupted state, and Qt warnings.

### Long-Running Process Recovery

- Database commits every `batch_size` files (default: 100)
- On crash at file #5,432, files #1-5,400 are safely saved
- Re-running auto-resumes from where it left off

### Two-Stage Hashing Optimization

For files ≥1MB:
1. Hash first 16KB (partial hash)
2. If no match → file is unique, calculate full hash
3. If match → verify with full hash (handles collisions)

Small files (<1MB): Direct full hash.

### Content-Based (Pixel) Hashing

Detects visually identical images that have different file hashes due to metadata changes.

**Algorithm:**
```python
def hash_image_content(file_path):
    """Calculate SHA-256 hash of normalized pixel content."""
    with Image.open(file_path) as img:
        img = ImageOps.exif_transpose(img)  # Apply EXIF rotation
        if img.mode != 'RGB':
            img = img.convert('RGB')
        pixel_data = img.tobytes()
        return hashlib.sha256(pixel_data).hexdigest()
```

**Key behaviors:**
- Returns `None` for videos (only images supported)
- Applies EXIF rotation before hashing (rotated images match originals)
- Converts to RGB for consistent comparison across color modes
- Stored in `UniquePhotos.content_hash` column

**Database methods (PhotoDatabase class):**
- `has_content_hash(content_hash)` - Check if content hash exists
- `get_files_by_content_hash(content_hash)` - Get all files with matching content hash
- `update_content_hash(file_hash, content_hash)` - Update content hash for existing record
- `get_files_without_content_hash(limit)` - Get files needing backfill
- `count_files_without_content_hash()` - Count for progress display

**Settings (DatabaseMetadata):**
- `is_content_hash_enabled()` - Check if content hashing is enabled
- `set_content_hash_enabled(enabled)` - Enable/disable content hashing
- Default: enabled

**find_duplicates() integration:**
```python
def find_duplicates(..., content_hash_enabled=True):
    # For each unique file (images only):
    # 1. Calculate content hash
    # 2. Check has_content_hash() for existing match
    # 3. If match: add to content_duplicate_files list
    # 4. Store content hash in database

    results["content_duplicate_files"] = content_duplicate_files
```

**Backfill worker (`ui/content_hash_worker.py`):**
```python
class ContentHashBackfillWorker(QThread):
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)
    completed = Signal(dict)  # {processed, skipped, errors, discovered_duplicates}
    error_occurred = Signal(str)
```

**UI integration:**
- System Settings tab: Enable checkbox + "Calculate Content Hashes" button
- Import History: "Content Duplicates" filter option (purple #9966CC)
- Photo Review: "Content Duplicates" view filter

### Archive Change Detection

Detects when archive files have been modified externally (e.g., edited in photo software outside PyPhotoOrganizer) by comparing current content hashes against stored values.

**How it works:**
1. User selects scope: entire archive or specific folder
2. Scanner compares current content hash vs. stored content hash for each file
3. On mismatch (external modification detected):
   - Original version located from backup or source_path
   - Original copied to Prior Revision Archive
   - Revision record created linking new hash to old hash
   - Operation logged as `'external_modification_detected'`

**Worker (`ui/archive_change_scanner_worker.py`):**
```python
class ArchiveChangeScannerWorker(QThread):
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)               # status message
    file_modified = Signal(dict)              # per-file modification notification
    completed = Signal(dict)                  # final results
    error_occurred = Signal(str)              # error message
```

**Database methods (PhotoDatabase class):**
- `get_archive_files_for_change_scan(scan_path, limit, offset)` - Get files with content hashes for scanning
- `count_archive_files_for_change_scan(scan_path)` - Count files for progress display

**UI location:** Archive Maintenance tab → "Archive Change Detection" group box

**Prerequisites checked at runtime:**
- Database loaded
- Backup location configured (warning if not)
- Prior Revision Archive configured (required)
- Files have content hashes (suggests backfill if many are NULL)

**Audit logging:**
- Operation: `'external_modification_detected'`
- Status: `'revision_created'`, `'original_not_found'`, `'failed'`
- Import History filter: "External Modifications"

### Hash History System (Schema v5)

When EXIF is modified, file hash changes. In Schema v5, all hashes (including revision hashes) are stored directly in `UniquePhotos` with `file_hash` as the primary key:

- Original file: `file_hash` = original hash, `revised_photo` = NULL
- Revision: `file_hash` = new hash, `revised_photo` = original hash, `revision_reason` = 'date_correction'

Duplicate detection uses a simple primary key lookup:
```python
# Check if hash exists (O(1) via indexed primary key)
is_duplicate = db.has_hash(file_hash)
```

The `get_all_historical_hashes()` method returns an empty set for backward compatibility, since all hashes are already in `get_all_hashes()`.

### Date Extraction Priority

**Images**: EXIF DateTimeOriginal → IPTC Date Created → OS metadata → Year 1000 fallback

**Videos**: ffprobe → mutagen → QuickTime atoms → OS metadata → Year 1000 fallback

**Unreliable dates** flagged when: no EXIF, year 1000, year < 1990, year > current+1, Unix epoch (1970-01-01), user-specified paths.

### Photo Filtering

`PhotoFilter` excludes non-photos based on:
- File size (default min: 50KB)
- Dimensions (default min: 800x600)
- Small squares (<400x400, likely icons)
- Filename patterns (favicon, icon, thumb, etc.)

**Videos bypass filtering entirely.**

### Override Skip Feature

The Import History tab includes an "Override Skip" button that allows users to import files that were previously filtered out (skipped due to file size, dimensions, etc.) by bypassing the PhotoFilter criteria.

**How it works:**

1. User selects files with `operation='skip_filtered'` in Import History
2. Clicking "Override Skip" validates selection and shows confirmation dialog (with total file size)
3. Selected rows are highlighted (yellow background) as visual feedback
4. Uses `ReprocessWorker` to import files directly (bypasses PhotoFilter)
5. Rows are removed in real-time as each file completes (success or duplicate)
6. Session view and scroll position are preserved after completion
7. Files are also added to albums if source directory has album association

**UI Features:**

| Feature | Description |
|---------|-------------|
| **Select All Visible** button | Quickly select all rows in current filtered view |
| **Override Skip** button | Import selected filtered files |
| **Undo Override** button | Undo last override skip (deletes files, removes DB entries, restores rows) |
| **"Recently Overridden" filter** | Show dropdown option to view files imported via Override Skip |
| **Visual feedback** | Yellow highlight on rows being processed, dimmed text |
| **Real-time removal** | Rows removed immediately as each file completes |
| **State preservation** | Session selection and scroll position preserved after operation |

**Key implementation:**

| Location | Component | Purpose |
|----------|-----------|---------|
| `ui/import_history_tab.py` | `override_skip_files()` | Main handler - validates selection, builds album mapping, preserves state, creates worker |
| `ui/import_history_tab.py` | `_on_override_skip_file_processed()` | Real-time row removal as files complete |
| `ui/import_history_tab.py` | `_on_override_skip_completed()` | Final cleanup, undo state storage, result message |
| `ui/import_history_tab.py` | `undo_last_override_skip()` | Undo capability - deletes files, removes DB entries, restores rows |
| `ui/import_history_tab.py` | `_select_all_visible()` | Select all rows in current view |
| `ui/reprocess_worker.py` | `ReprocessWorker` | Extended with `file_processed` signal for per-file notifications |

**FileLogTableModel enhancements:**

| Method | Purpose |
|--------|---------|
| `removeRowsBySourcePath(paths)` | Remove rows matching source paths |
| `markRowsAsProcessing(paths)` | Mark rows with yellow background during processing |
| `clearProcessingFlags()` | Clear all processing visual state |

**ReprocessWorker signals:**

```python
# Existing signals
progress_update = Signal(int, int, str)  # current, total, filename
status_update = Signal(str)              # status message
completed = Signal(dict)                 # results dictionary
error_occurred = Signal(str)             # error message

# New signal for real-time UI updates
file_processed = Signal(str, str)        # source_path, result ('success', 'skipped', 'failed')
```

**Album support in ReprocessWorker:**

The `ReprocessWorker` constructor accepts optional album parameters:
```python
ReprocessWorker(
    database_path=...,
    file_records=...,
    archive_location=...,
    organization_template=...,
    copy_mode=True,
    audit_manager=...,
    album_manager=album_manager,           # Optional: AlbumManager instance
    source_album_mapping=source_album_mapping  # Optional: {source_path: {'album_id': int, 'enable_sub_albums': bool}}
)
```

After successful database insert, ReprocessWorker:
1. Finds matching source directory from `source_album_mapping`
2. Handles sub-albums if enabled (creates if needed)
3. Adds file to album via `AlbumManager.add_photo_to_album()`
4. Logs album info to audit trail (album_name, album_path, sub_album_name)
5. Emits `file_processed` signal for real-time UI updates

**Undo Capability:**

The `undo_last_override_skip()` method allows reversing the last override skip operation:
1. Deletes imported files from the archive
2. Removes entries from UniquePhotos database table
3. Restores rows to the filtered view
4. Clears the recently overridden list for undone files
5. Source files are never affected (read-only policy)

**State preservation tracking:**

```python
# Stored before operation starts
self._preserved_session_id = current_session_id
self._preserved_scroll_position = view.verticalScrollBar().value()
self._preserved_selection_paths = {source_paths...}

# Restored after completion
self._last_override_skip_results = results  # For undo capability
self._recently_overridden_logs.append(...)  # For filter
```

**UI Guidelines (per project rules):**

- All buttons always enabled (never grayed out)
- If no selection: shows `QMessageBox.information()` with guidance
- If selection contains non-filtered files: shows informative message with tip
- If source files missing: warns user but continues with valid files
- Confirmation dialog shows file count and total size

### Organization Templates

Folder structure templates with placeholders:
- `{year}`, `{month}`, `{day}` - numeric
- `{month_name}`, `{month_sname}` - full/abbreviated month names
- `{day_name}`, `{day_sname}` - full/abbreviated day names

Example: `{year}/{month}-{month_sname}/{day}` → `2025/01-Jan/15/`

### Filename Templates

Optional renaming during import:
- `{year}`, `{month}`, `{day}`, `{hour}`, `{minute}`, `{second}`
- `{original_name}`, `{original_name_no_ext}`, `{ext}`
- `{counter}`, `{counter:04d}` - sequential with padding

### Prior Revision Archive

When rotating images:
1. Original moved to Prior Revision Archive (with hash suffix in filename)
2. Rotated version placed in main archive (same path as original)
3. Both tracked in database for undo capability
4. All revision hashes added to `FileHashHistory` for duplicate detection

Configure via `DatabaseMetadata.set_prior_revision_archive_location()`.

### Albums System

Albums are photo collections stored in separate locations (ideal for photo frames):
- Per-album storage locations
- Flat file structure (no date subfolders)
- `sync_deletions` option: auto-remove when deleted from archive
- `AlbumManager` handles CRUD and photo operations
- Can be associated with source directories for automatic import-time additions

### Source Directory Album Association

Allows automatic album population during import by associating albums with source directories.

**Database Schema:**

```sql
-- SourceDirectories table (extended columns)
album_id INTEGER,                    -- FK to Albums.id, NULL = no association
enable_sub_albums INTEGER DEFAULT 0  -- 0 = disabled, 1 = create sub-albums

-- SourceDirectorySubAlbums table (tracks auto-created sub-albums)
CREATE TABLE SourceDirectorySubAlbums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_directory_id INTEGER NOT NULL,
    parent_album_id INTEGER NOT NULL,
    sub_album_id INTEGER NOT NULL,
    relative_subdir_path TEXT NOT NULL,
    created_timestamp TEXT NOT NULL,
    UNIQUE(source_directory_id, relative_subdir_path)
);
```

**UI Components:**

The source directory table in Import Settings includes two additional columns:
- **Album dropdown**: Select album or "(None)" or "+ New Album..."
- **Sub-Albums checkbox**: Enable automatic sub-album creation (only enabled when album selected)

`NewAlbumDialog` allows creating albums directly from the import settings without switching tabs.

**Import Flow Integration:**

Hook point in `main.py:organize_files()` after successful file copy:

```
For each file successfully copied to archive:
1. Find matching source directory from source_album_mapping
2. If source has album association:
   a. If sub-albums disabled: add to parent album
   b. If sub-albums enabled AND file is in subdirectory:
      - Derive sub-album name: "{Parent Album} - {Subdir1} - {Subdir2}"
      - Get existing or create new sub-album
      - Sub-album storage: parent_storage/{relative_subdir}/
      - Track mapping in SourceDirectorySubAlbums table
      - Add file to sub-album
   c. Copy file to album storage via AlbumManager.add_photo_to_album()
```

**Sub-Album Naming Convention:**

| Source Path | File Location | Sub-Album Name |
|-------------|---------------|----------------|
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/Camera/pic.jpg` | "Phone - Camera" |
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/Screenshots/img.png` | "Phone - Screenshots" |
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/WhatsApp/Media/photo.jpg` | "Phone - WhatsApp - Media" |

**Key Methods:**

| Location | Method | Purpose |
|----------|--------|---------|
| `database_metadata.py` | `update_source_album()` | Set/clear album association |
| `database_metadata.py` | `update_source_sub_albums_enabled()` | Toggle sub-albums |
| `database_metadata.py` | `get_or_create_sub_album()` | Track sub-album mappings |
| `import_settings_tab.py` | `get_source_album_mapping()` | Build mapping for worker |
| `import_settings_tab.py` | `_create_new_album()` | Dialog-based album creation |
| `main.py` | `organize_files()` | Album addition after copy |
| `album_manager.py` | `add_photo_to_album()` | Copy file to album storage |

**Error Handling:**

- Album failures are non-fatal (logged, import continues)
- If album storage unavailable, skip album addition
- If sub-album creation fails, fall back to parent album
- Results include `total_album_additions` count

### Theme System

`ThemeManager` singleton with light/dark mode:
```python
from ui.theme import get_theme
theme = get_theme()
self.setStyleSheet(theme.get_global_stylesheet())
```

### Audit System

`AuditManager` tracks import sessions and file operations:
- `start_session()` / `end_session()` for session lifecycle
- `log_file_operation()` for per-file tracking
- `record_duplicate()` for duplicate relationships
- Export to JSON/CSV via Import History tab

## Settings Configuration

`settings.json` example:
```json
{
  "source_directory": ["D:\\Photos"],
  "destination_directory": "I:\\Archive",
  "database_path": "PhotoDB.db",
  "batch_size": 100,
  "include_subdirectories": true,
  "file_endings": [".jpg", ".png", ".heic", ".mov", ".mp4"],
  "copy_files": true,
  "partial_hash_enabled": true,
  "photo_filter_enabled": true,
  "min_file_size": 51200,
  "min_width": 800,
  "min_height": 600
}
```

## Logging

All modules use `utils.setup_logger()` with:
- Console output (DEBUG level)
- Rotating file handler (5MB max, 3 backups)

Log files: `main_app_error.log`, `DuplicateFileDetection_app_error.log`, etc.

### Performance Profiling

```python
from utils import profile_function, profile_block

@profile_function(logger)
def my_function(): ...

with profile_block("Database query", logger):
    results = db.query()
```

## Dependencies

- `PIL` (Pillow): Image processing, EXIF
- `pillow_heif`: HEIC/HEIF support
- `piexif`: EXIF writing
- `PySide6`: Qt GUI framework
- `tqdm`: Progress bars

## Key Gotchas & Rules

1. **Source files are sacred** - never modify them
2. **WAL mode required** - prevents "database is locked" errors
3. **Videos bypass PhotoFilter** - PIL can't open them
4. **Hash changes after EXIF write** - use `FileHashHistory` for duplicate detection
5. **Buttons never disabled** - always clickable, show message if action unavailable
6. **`get_metadata()` must SELECT all columns** - including `enable_file_rename`, `filename_template`
7. **Callbacks return stop signal** - `progress_callback()` returns `True` to stop processing
8. **EXIF orientation** - use `ImageOps.exif_transpose()` when loading images for display
9. **Config passed to worker** - database-bound settings must be explicitly added to config dict
10. **Content hashing for images only** - `hash_image_content()` returns `None` for videos
11. **Dialog worker cleanup** - dialogs with QThread workers must implement `closeEvent` with `worker.wait()`
12. **Large byte values in signals** - use `object` type instead of `int` for byte counts >2GB to avoid 32-bit overflow

## Known Issues

- Files with apostrophes in path may fail
- Need hash verification after vault copy
