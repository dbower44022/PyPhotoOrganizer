# CLAUDE.md

Guidance for Claude Code when working with this repository. **For end-user docs, see [USER_GUIDE.md](USER_GUIDE.md).**

## Related Documentation

| Document | Contents |
|----------|----------|
| [CLAUDE_DATABASE.md](CLAUDE_DATABASE.md) | Schema definitions, health/backup/recovery systems |
| [CLAUDE_WORKERS.md](CLAUDE_WORKERS.md) | Worker thread patterns, cleanup requirements |
| [CLAUDE_FEATURES.md](CLAUDE_FEATURES.md) | Detailed feature implementations |
| [CLAUDE_DATE_EXTRACTION.md](CLAUDE_DATE_EXTRACTION.md) | Date extraction algorithm, EXIF handling |

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
| `main.py` | Orchestration: `organize_files()`, `perform_metadata_upgrades()` |
| `DuplicateFileDetection.py` | `PhotoDatabase`, `find_duplicates()`, `get_creation_date()`, hashing functions, metadata scoring |
| `database_metadata.py` | `DatabaseMetadata`: archive binding, source dirs, settings |
| `config.py` | `Config`: settings loading with defaults |
| `photo_filter.py` | `PhotoFilter`: filters icons/thumbnails by size/dimensions |
| `exif_writer.py` | `write_exif_date()`, `read_exif_date()` |
| `audit_manager.py` | `AuditManager`: session tracking, file operation logging |
| `album_manager.py` | `AlbumManager`: album CRUD, photo-to-album operations |
| `path_resolver.py` | `PathResolver`: relative↔absolute path resolution |
| `storage_backend.py` | `StorageBackend` ABC, `LocalStorageBackend`, `StorageManager` |
| `storage_backend_s3.py` | `S3StorageBackend`: Amazon S3 cloud storage |
| `cloud_sync_manager.py` | `CloudSyncManager`: upload queue, sync tracking |
| `cloud_sync.py` | `CloudSync`: high-level sync orchestration, conflict resolution |

### GUI Modules (ui/)

| Module | Purpose |
|--------|---------|
| `main_window.py` | Main window, 6-tab interface |
| `import_settings_tab.py` | Source folders, album associations, Start/Stop |
| `archive_settings_tab.py` | Organization template, file renaming |
| `system_settings_tab.py` | Database info, copy/move mode, performance |
| `progress_tab.py` | Real-time progress display |
| `import_history_tab.py` | Session history, file preview, export |
| `worker.py` | `ProcessingWorker` background thread |
| `theme.py` | `ThemeManager`, light/dark mode |
| `cloud_settings_widget.py` | Cloud storage configuration per vault |
| `cloud_sync_worker.py` | `CloudSyncWorker`: background sync with pause/resume |

See [CLAUDE_WORKERS.md](CLAUDE_WORKERS.md) for full worker list and patterns.

### Database Tables (Quick Reference)

| Table | Purpose |
|-------|---------|
| `UniquePhotos` | File hashes, paths, dates, metadata quality |
| `SourceDirectories` | Source folder configs with album associations |
| `UnreliableDates` | Files with questionable dates |
| `Albums` / `AlbumPhotos` | Album system |
| `ImportSession` / `FileProcessingLog` | Audit trail |
| `MetadataUpgradeHistory` | Archive upgrade tracking |

See [CLAUDE_DATABASE.md](CLAUDE_DATABASE.md) for full schema details.

## Processing Flow

1. `get_file_list()` scans sources for media files
2. `PhotoFilter` excludes icons/thumbnails (videos pass through)
3. `find_duplicates()` hashes files, checks database, identifies upgrade candidates
4. `organize_files()` copies unique files to archive with date-based folders
5. `perform_metadata_upgrades()` replaces inferior archive files with better duplicates
6. Database updated with hashes, paths, and metadata quality scores

## Key Features (Quick Reference)

| Feature | Description | Details |
|---------|-------------|---------|
| Two-Stage Hashing | Partial hash (16KB) for large files, full hash on match | Built-in |
| Content Hashing | Pixel-based duplicate detection | [CLAUDE_FEATURES.md](CLAUDE_FEATURES.md) |
| Metadata Upgrades | Replace archive files when duplicate has better EXIF | [CLAUDE_FEATURES.md](CLAUDE_FEATURES.md) |
| Override Skip | Import previously filtered files | [CLAUDE_FEATURES.md](CLAUDE_FEATURES.md) |
| Album Association | Auto-add to albums during import | [CLAUDE_FEATURES.md](CLAUDE_FEATURES.md) |
| Archive Change Detection | Detect external file modifications | [CLAUDE_FEATURES.md](CLAUDE_FEATURES.md) |

## Photo Filtering

`PhotoFilter` excludes non-photos:
- File size (default min: 50KB)
- Dimensions (default min: 800x600)
- Small squares (<400x400, likely icons)
- Filename patterns (favicon, icon, thumb)

**Videos bypass filtering entirely.**

## Organization Templates

Folder structure placeholders: `{year}`, `{month}`, `{day}`, `{month_name}`, `{month_sname}`, `{day_name}`, `{day_sname}`

Example: `{year}/{month}-{month_sname}/{day}` → `2025/01-Jan/15/`

## Filename Templates

Optional renaming: `{year}`, `{month}`, `{day}`, `{hour}`, `{minute}`, `{second}`, `{original_name}`, `{original_name_no_ext}`, `{ext}`, `{counter}`, `{counter:04d}`

## Prior Revision Archive

When modifying archive files (rotation, EXIF edit, metadata upgrade):
1. Original moved to Prior Revision Archive (with hash suffix)
2. Modified version placed in main archive
3. Both tracked in database via `revised_photo` column

## Albums System

- Per-album storage locations (ideal for photo frames)
- Flat file structure (no date subfolders)
- `sync_deletions` option: auto-remove when deleted from archive
- Can be associated with source directories for automatic import-time additions

## Audit System

`AuditManager` tracks import sessions and file operations:
- `start_session()` / `end_session()` for session lifecycle
- `log_file_operation()` for per-file tracking
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
  "copy_files": true
}
```

## Logging

All modules use `utils.setup_logger()` with rotating file handler (5MB, 3 backups).

```python
from utils import profile_function, profile_block

@profile_function(logger)
def my_function(): ...

with profile_block("Database query", logger):
    results = db.query()
```

## Dependencies

`PIL` (Pillow), `pillow_heif`, `piexif`, `PySide6`, `tqdm`

## Key Gotchas & Rules

1. **Source files are sacred** - never modify them
2. **WAL mode required** - all DB connections must use WAL mode
3. **Videos bypass PhotoFilter** - PIL can't open them
4. **Hash changes after EXIF write** - revisions stored with `revised_photo` linking to original
5. **Buttons never disabled** - always clickable, show message if unavailable
6. **`get_metadata()` must SELECT all columns** - including `enable_file_rename`, `filename_template`
7. **Callbacks return stop signal** - `progress_callback()` returns `True` to stop
8. **EXIF orientation** - use `ImageOps.exif_transpose()` for display
9. **Config passed to worker** - database settings must be in config dict
10. **Content hashing images only** - `hash_image_content()` returns `None` for videos
11. **Dialog worker cleanup** - must implement `closeEvent` with `worker.wait()` (see [CLAUDE_WORKERS.md](CLAUDE_WORKERS.md))
12. **Large byte values** - use `Signal(object)` not `Signal(int)` for >2GB
13. **Metadata upgrades protect user edits** - files with `revision_reason='date_correction'` never replaced
14. **Metadata quality stored at import** - `date_source`, `date_reliable`, `metadata_quality_score` set in `insert_unique_photo()`

## Known Issues

- Files with apostrophes in path may fail
- Need hash verification after vault copy
