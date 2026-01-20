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
| `DuplicateFileDetection.py` | `PhotoDatabase`, `find_duplicates()`, `get_creation_date()`, `hash_file()` |
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
| `import_settings_tab.py` | Source folders, filtering, Start/Stop buttons |
| `archive_settings_tab.py` | Organization template, file renaming |
| `system_settings_tab.py` | Database info, copy/move mode, performance |
| `progress_tab.py` | Real-time progress display |
| `import_history_tab.py` | Session history, file preview, export |
| `worker.py` | `ProcessingWorker` background thread |
| `theme.py` | `ThemeManager`, light/dark mode support |

### Database Tables

All tables in SQLite database (default: `PhotoDB.db`):

| Table | Purpose |
|-------|---------|
| `DatabaseMetadata` | Archive location, settings, schema version |
| `UniquePhotos` | File hashes, paths, creation dates |
| `SourceDirectories` | Persistent source folder configs |
| `UnreliableDates` | Files with questionable dates |
| `FileHashHistory` | Hash history for duplicate detection after EXIF edits |
| `FileRenameHistory` | Original→renamed filename mappings |
| `DeletedFiles` | Soft-delete tracking with restore capability |
| `FileVersions` | Revision history for rotations/edits |
| `Albums` | Album metadata |
| `AlbumPhotos` | Album-to-photo junction table |
| `ImportSession` | Audit session tracking |
| `FileProcessingLog` | Per-file operation audit log |
| `DuplicateMapping` | Original-to-duplicate relationships |

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

### Hash History System

When EXIF is modified, file hash changes. `FileHashHistory` table preserves original hashes so the file is still detected as duplicate if re-imported.

```python
# After EXIF write:
db.add_hash_to_history(old_hash, new_hash, reason='date_correction')
```

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

## Known Issues

- Files with apostrophes in path may fail
- Need hash verification after vault copy
