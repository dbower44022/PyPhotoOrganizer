# Photo Triage Application

High-performance photo review and organization tool for PyPhotoOrganizer.

## Features

✅ **Zero-lag scrolling** - Handle 100,000+ images smoothly
✅ **Virtual scrolling** - Only renders visible thumbnails
✅ **Three-tier caching** - Memory → Disk → Original files
✅ **Keyboard shortcuts** - Rapid marking with D/F/C keys
✅ **Folder browser** - Navigate archive by year/month/day
✅ **Large preview** - Zoomable image preview with EXIF metadata
✅ **Batch operations** - Mark multiple files, export lists

## Quick Start

### 1. Launch Application

```bash
cd /path/to/PyPhotoOrganizer
python triage/main_triage.py
```

Or with a specific database:

```bash
python triage/main_triage.py --db PhotoDB.db
```

### 2. Select Database

- Click "Browse..." in the toolbar
- Select your PyPhotoOrganizer database (`.db` file)
- The archive location will load automatically

### 3. Browse Folders

- Expand year folders in the left panel (2025 → 01 → 15)
- Click a folder to load thumbnails

### 4. Review Photos

- **Scroll** through thumbnails
- **Select** images (click, Shift+click for range, Ctrl+click for individual)
- **Mark** with keyboard shortcuts:
  - `D` - Toggle delete mark (red X overlay)
  - `F` - Toggle favorite mark (gold star overlay)
  - `C` - Flag for date correction (calendar overlay)
- **Change grid size**: `1` (small), `2` (medium), `3` (large)
- **Preview**: Click image or press `Space` for large preview

### 5. Export Marked Files

- **Actions → Export Marked Files**
- Save list to text file for batch processing

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **D** | Toggle delete mark (red X) |
| **F** | Toggle favorite mark (gold star) |
| **C** | Flag for date correction (calendar) |
| **1** | Small thumbnails (128px) |
| **2** | Medium thumbnails (256px) |
| **3** | Large thumbnails (512px) |
| **Space** | Show large preview |
| **Arrow keys** | Navigate grid |
| **Ctrl+A** | Select all |
| **Escape** | Clear selection |
| **Shift+Click** | Range select |
| **Ctrl+Click** | Toggle individual selection |
| **Ctrl+Wheel** | Zoom preview |
| **Double-click** | Reset preview zoom |

## Window Layout

```
┌─────────────────────────────────────────────────────────┐
│  [Database ▼] [Browse] [Folder: /archive/2025/]  Stats │
├────────────┬────────────────────────────────────────────┤
│  Folders   │     Thumbnail Grid                         │
│  ├─ 2025/  │     ┌────┬────┬────┬────┐                 │
│  │  ├─01/  │     │ ⭐ │    │ ❌ │    │                 │
│  │  │ ├15/ │     │img1│img2│img3│img4│                 │
│  │  │ └16/ │     └────┴────┴────┴────┘                 │
│  │  ├─02/  │     (Zero lag, smooth scrolling)          │
│  │  └─03/  │                                            │
├────────────┴────────────────────────────────────────────┤
│  Preview: vacation_001.jpg                              │
│  ┌──────────────────┐  Size: 5.2 MB                     │
│  │                  │  Date: 2025-02-15                  │
│  │   Large Image    │  Camera: Canon EOS R5              │
│  │  (Ctrl+Wheel to  │  EXIF: ISO 400  F/2.8  1/500s      │
│  │   zoom, drag to  │                                    │
│  │   pan)           │                                    │
│  └──────────────────┘                                    │
└─────────────────────────────────────────────────────────┘
```

## How Marking Works

### Database-Only Marks

**Important**: Triage marks files in the **database only** - no files are deleted or moved!

1. **Mark files** with keyboard shortcuts (D/F/C)
2. **Export list** to text file
3. **Review** marked files in main PyPhotoOrganizer
4. **Process** marked files (delete, copy favorites, correct dates)

### Mark Types

**Delete** (D key):
- Red X overlay
- Track files to be removed from archive
- Export list for batch deletion

**Favorite** (F key):
- Gold star overlay
- Mark best photos from session/event
- Export list for copying to favorites folder

**Date Correction** (C key):
- Calendar overlay
- Flag files with wrong dates
- Review in Date Corrections tab of main app

## Performance

### Optimizations

- **Virtual scrolling**: Only ~20-50 widgets for 100,000+ images
- **Three-tier cache**:
  - L1: 500 thumbnails in RAM (<1ms access)
  - L2: 5GB on disk (50-100ms access)
  - L3: Generate from original (async, placeholder)
- **Prefetching**: Loads visible + next/previous 50 items
- **Background generation**: 8 worker threads, non-blocking
- **LRU eviction**: Automatic cache management

### Expected Performance

| Operation | Target Time |
|-----------|-------------|
| Load 10,000 folder | <200ms |
| Scroll frame rate | 60 FPS (16ms) |
| Memory cache hit | <1ms |
| Disk cache hit | 50-100ms |
| Mark operation | <10ms |
| Memory usage | <500MB |

## Configuration

Configuration file: `triage/triage_config.json`

```json
{
  "database_path": "PhotoDB.db",
  "thumbnail_cache_dir": "/tmp/ppo_triage_cache",
  "memory_cache_size": 500,
  "disk_cache_size_gb": 5,
  "default_thumbnail_size": "medium",
  "prefetch_count": 50,
  "worker_threads": 8
}
```

### Settings

- **thumbnail_cache_dir**: Disk cache location (default: `/tmp/ppo_triage_cache`)
- **memory_cache_size**: Max thumbnails in RAM (default: 500)
- **disk_cache_size_gb**: Max disk cache size (default: 5GB)
- **worker_threads**: Background generation threads (default: 8)
- **prefetch_count**: Items to prefetch on scroll (default: 50)

## Workflow Examples

### Example 1: Delete Duplicates/Mistakes

1. Open vacation folder: `/archive/2025/07/`
2. Scroll through photos
3. Press `D` on duplicates, blurry shots, mistakes
4. Export marked list: **Actions → Export Marked Files**
5. Review list in text editor
6. Batch delete in file manager

### Example 2: Select Event Highlights

1. Open event folder: `/archive/2025/08/15/` (wedding)
2. Press `F` on best photos
3. Export favorites list
4. Copy marked files to favorites archive

### Example 3: Flag Date Issues

1. Open folder with scanned photos
2. Review dates (shown in preview metadata)
3. Press `C` on photos with wrong dates
4. Open main PyPhotoOrganizer
5. **Date Corrections tab** → Batch correct dates

## Troubleshooting

### Thumbnails Show "Loading..."

**Cause**: Files exist in database but not on disk

**Fix**:
1. Check archive location in database metadata
2. Verify files exist at expected paths
3. Check file permissions

### Slow Performance

**Cause**: First-time thumbnail generation

**Solution**:
- Wait for initial generation (background process)
- Thumbnails cached to disk for future sessions
- Use smaller grid size (1) during first run

### High Memory Usage

**Cause**: Memory cache too large

**Fix**: Reduce `memory_cache_size` in config (default: 500)

### Database Not Found

**Cause**: Database file moved or deleted

**Fix**:
1. Use **File → Open Database** to browse
2. Select correct `.db` file
3. Verify archive location is accessible

## Technical Details

### Architecture

```
TriageWindow
    ├─ FolderBrowser (tree view)
    ├─ ThumbnailGridView (virtual scrolling)
    │   ├─ ThumbnailGridModel (QAbstractListModel)
    │   └─ ThumbnailDelegate (custom rendering)
    ├─ PreviewPane (zoomable image + EXIF)
    └─ ThumbnailCache (three-tier caching)
        └─ ThumbnailWorker (background generation)
```

### Database Schema

**TriageActions** - Track marking actions:
```sql
CREATE TABLE TriageActions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    action_type TEXT NOT NULL,  -- 'delete', 'favorite', 'date_correction'
    marked_timestamp TEXT NOT NULL,
    unmarked_timestamp TEXT,
    notes TEXT
);
```

**ThumbnailCache** - Disk cache tracking:
```sql
CREATE TABLE ThumbnailCache (
    file_hash TEXT NOT NULL UNIQUE,
    thumbnail_path TEXT NOT NULL,
    thumbnail_size INTEGER NOT NULL,
    last_accessed_timestamp TEXT NOT NULL
);
```

### Files Structure

```
triage/
├── main_triage.py              # Entry point
├── triage_config.py            # Configuration
├── triage_database.py          # Database helpers
├── thumbnail_cache.py          # Three-tier caching
├── thumbnail_generator.py      # Background workers
├── ui/
│   ├── triage_window.py        # Main window
│   ├── thumbnail_grid_view.py  # Grid view
│   ├── thumbnail_grid_model.py # Data model
│   ├── thumbnail_delegate.py   # Custom renderer
│   ├── folder_browser.py       # Folder tree
│   └── preview_pane.py         # Image preview
└── migrate_database.sql        # Database schema
```

## Development

### Running Tests

```bash
# GUI test with 1000 test images
python triage/test_grid_performance.py --count 1000

# Core component tests (no GUI)
python3 triage/test_grid_core.py
```

### Debug Mode

```bash
python triage/main_triage.py --debug
```

Logs written to: `triage_app.log`

## Requirements

- Python 3.8+
- PySide6 >= 6.4.0
- Pillow >= 10.0.0
- Existing PyPhotoOrganizer database

## Credits

Part of **PyPhotoOrganizer** - Photo duplicate detection and organization system.

Built with:
- Python
- PySide6 (Qt for Python)
- PIL/Pillow (image processing)
- SQLite (database)

## License

Same as PyPhotoOrganizer.

---

**Ready to triage!** 🎉

For more information, see the main PyPhotoOrganizer documentation.
