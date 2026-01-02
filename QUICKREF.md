# Quick Reference Guide

> One-page cheat sheet for PyPhotoOrganizer (GUI + CLI)

**Last Updated:** 2026-01-02

---

## Installation

```bash
pip install -r requirements.txt
```

This installs:
- Pillow (image processing)
- pillow-heif (HEIC support)
- tqdm (CLI progress bars)
- PySide6 (GUI interface)

---

## Quick Start

### GUI Mode (Recommended)

**Launch:**
```bash
python main_gui.py
```

**Workflow:**
1. **Setup Tab** → Add source folders → Select destination
2. **Settings Tab** (optional) → Adjust configuration
3. **Setup Tab** → Click "Start Processing"
4. **Progress Tab** → Monitor real-time progress
5. **Results Tab** → View statistics and export

### CLI Mode

**1. Create settings.json:**
```json
{
  "source_directory": ["path/to/photos"],
  "destination_directory": "path/to/output"
}
```

**2. Run:**
```bash
python main.py
```

---

## Essential Settings

```json
{
  "source_directory": ["D:\\Photos"],       // Required
  "destination_directory": "E:\\Organized",  // Required
  "copy_files": true,                       // Copy mode
  "move_files": false,                      // Move mode
  "batch_size": 100,                        // Checkpoint frequency
  "photo_filter_enabled": true              // Filter icons/thumbnails
}
```

---

## Common Configurations

### Safe Mode (Recommended for First Run)
```json
{
  "source_directory": ["test_photos"],
  "destination_directory": "test_output",
  "copy_files": true,
  "move_files": false,
  "batch_size": 50
}
```

### Performance Mode
```json
{
  "batch_size": 500,
  "partial_hash_enabled": true,
  "photo_filter_enabled": true
}
```

### Move Mode (⚠️ Destructive)
```json
{
  "copy_files": false,
  "move_files": true
}
```

---

## File Organization

| Setting | Result |
|---------|--------|
| `group_by_year: true, group_by_day: true` | `2024/11/25/photo.jpg` |
| `group_by_year: true, group_by_day: false` | `2024/11/photo.jpg` |
| `group_by_year: false, group_by_day: true` | `2024-11/25/photo.jpg` |
| `group_by_year: false, group_by_day: false` | `2024-11/photo.jpg` |

---

## Photo Filtering

### Enable/Disable
```json
{
  "photo_filter_enabled": true  // false to disable
}
```

### Common Presets

**Strict (HD Photos Only):**
```json
{
  "min_file_size": 102400,
  "min_width": 1920,
  "min_height": 1080,
  "require_exif": true
}
```

**Permissive (Include More):**
```json
{
  "min_file_size": 10240,
  "min_width": 640,
  "min_height": 480,
  "require_exif": false
}
```

---

## Performance Tuning

| Scenario | batch_size | partial_hash | filter |
|----------|------------|--------------|--------|
| Fast, reliable system | 500 | true | true |
| Default | 100 | true | true |
| Safety first | 50 | true | true |
| Maximum performance | 1000 | true | true |

---

## Commands

### Run GUI
```bash
python main_gui.py
```

### Run CLI
```bash
python main.py
```

### Check Database
```bash
sqlite3 PhotoDB.db
SELECT COUNT(*) FROM UniquePhotos;
.quit
```

### View Logs
```bash
# Windows
type main_app_error.log
# Linux/Mac
tail -f main_app_error.log

# Or use GUI Logs tab for real-time viewing
```

---

## Common Tasks

### Process Multiple Folders
```json
{
  "source_directory": [
    "D:\\iPhone Backup",
    "D:\\Android Backup",
    "E:\\Old PC"
  ]
}
```

### Skip Subdirectories
```json
{
  "include_subdirectories": false
}
```

### Process Only Photos (No Videos)
```json
{
  "file_endings": [".jpg", ".jpeg", ".png", ".heic"]
}
```

### Process Only Videos
```json
{
  "file_endings": [".mov", ".mp4", ".avi"]
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Files not found | Check `source_directory` path |
| Permission denied | Run as administrator (Windows) or use `sudo` (Linux) |
| Slow processing | Enable `partial_hash_enabled: true` |
| Too many icons | Enable `photo_filter_enabled: true` |
| Database locked | Close other instances |
| Out of space | Check destination drive space |

---

## Important Notes

✅ **DO:**
- Backup before using move mode
- Test with small dataset first
- Use copy mode initially
- Keep database backed up
- Monitor first 100 files

❌ **DON'T:**
- Use both copy AND move mode
- Delete database during processing
- Modify source files during run
- Use `..` in paths
- Run multiple instances simultaneously

---

## File Locations

```
PyPhotoOrganizer/
├── settings.json        # Your configuration
├── PhotoDB.db          # Database (backup this!)
├── main.py             # Run this
├── *.log              # Log files
└── README.md          # Full documentation
```

---

## Constants Reference

```python
# File I/O
FILE_READ_CHUNK_SIZE = 4096

# Hashing
PARTIAL_HASH_BYTES = 16384        # 16KB
PARTIAL_HASH_MIN_FILE_SIZE = 1MB

# Database
DEFAULT_BATCH_SIZE = 100

# Photo Filtering
MIN_PHOTO_FILE_SIZE = 51200       # 50KB
MIN_PHOTO_WIDTH = 800
MIN_PHOTO_HEIGHT = 600
MIN_SQUARE_SIZE = 400
```

---

## Progress Output

```
Scanning directories: 100%|████| 3/3
Processing files: 100%|████| 1500/1500 [05:30, 4.5file/s]
Organizing files: 100%|████| 850/850 [02:15, 6.3file/s]
```

**Interpretation:**
- **Scanning**: Finding files
- **Processing**: Hash calculation + duplicate detection
- **Organizing**: Copy/move to destination

---

## Recovery

### Application Crashed?
```bash
# Just re-run, it will resume
python main.py
```

### Reset Database?
```bash
# Backup first!
cp PhotoDB.db PhotoDB.db.backup
rm PhotoDB.db
python main.py  # Rebuild from scratch
```

---

## Validation Rules

✅ **Valid:**
```json
{
  "source_directory": ["D:\\Photos"],
  "destination_directory": "E:\\Output",
  "copy_files": true,
  "move_files": false
}
```

❌ **Invalid:**
```json
{
  "source_directory": "../../../system",  // No ..
  "copy_files": true,
  "move_files": true  // Can't both be true
}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error occurred (check logs) |

---

## Quick Formulas

### Estimated Time
```
Time ≈ (file_count × avg_file_size) / disk_speed
Example: (10,000 × 2MB) / 100MB/s ≈ 200 seconds
```

### Database Size
```
DB_size ≈ file_count × 200 bytes
Example: 10,000 files ≈ 2MB database
```

### Batch Size Tuning
```
Checkpoint_frequency = batch_size × avg_process_time
Example: 100 files × 1s/file = 100s between checkpoints
```

---

## Keyboard Shortcuts

**During Execution:**
- `Ctrl+C`: Gracefully stop (commits current batch)
- Database auto-saves every `batch_size` files

---

## Default Values

All optional settings have defaults. Minimal config:

```json
{
  "source_directory": ["path"],
  "destination_directory": "path"
}
```

Everything else uses defaults from `constants.py`.

---

## Version 2.0 Features

✅ **New in v2.0:**
- Path traversal protection
- Photo filtering system
- Database indexes
- Constants module
- Bug fixes (HEIC, move mode, temp files)

---

## GUI Quick Reference

### Setup Tab
- **Add Folder**: Select source directories
- **Remove Selected**: Remove selected source
- **Browse**: Choose destination directory
- **Copy/Move**: Choose operation mode
- **Start/Stop**: Control processing

### Progress Tab
- **Overall Progress**: Total completion percentage
- **Stage Progress**: Current stage (Scanning/Processing/Organizing)
- **Time Estimates**: Elapsed and remaining time
- **Status Log**: Recent events with timestamps

### Results Tab
- **Summary Statistics**: Files examined, originals, duplicates, filtered
- **Breakdown Tree**: Expandable categories
- **Export Results**: Save to JSON or CSV

### Logs Tab
- **Level Filter**: Filter by DEBUG/INFO/WARNING/ERROR
- **Search**: Find specific log entries
- **Auto-scroll**: Follow latest logs
- **Refresh**: Reload from log files

### Settings Tab
- **Load/Save**: Manage settings.json
- **Restore Defaults**: Reset to defaults
- **Validate**: Check settings validity
- **Preview**: See folder structure example

---

## Getting Help

**Documentation:**
- [README.md](README.md) - Overview
- [CONFIGURATION.md](CONFIGURATION.md) - All settings
- [ARCHITECTURE.md](ARCHITECTURE.md) - How it works
- [API.md](API.md) - Code reference
- [DEVELOPMENT.md](DEVELOPMENT.md) - Contributing
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Fix issues
- [GUI_TESTING_GUIDE.md](GUI_TESTING_GUIDE.md) - GUI testing

**Support:**
- GitHub Issues
- Documentation files

---

## Example Session

```bash
# 1. Setup
$ python main.py
Configuration loaded successfully
Found 1500 files for processing

# 2. Progress
Scanning directories: 100%|████| 3/3 [00:02<00:00]
Processing files: 100%|████| 1500/1500 [05:30<00:00, 4.5file/s]
Organizing files: 100%|████| 850/850 [02:15<00:00, 6.3file/s]

# 3. Results
Completed Processing
Total files examined: 1500
  - New original photos: 850
  - Duplicates: 600
  - Filtered (non-photos): 50
```

---

## Performance Tips

1. **Use SSD** for database
2. **Enable filtering** to skip icons
3. **Increase batch size** for speed
4. **Use local drives** not network
5. **Close other programs** using disk
6. **Enable partial hashing** for large files

---

## Safety Checklist

Before large run:
- [ ] Backup important photos
- [ ] Use copy mode first
- [ ] Test with 10-20 files
- [ ] Verify dates are correct
- [ ] Check destination has space
- [ ] Backup database file

---

**Print this page for quick reference!**

*Last updated: 2026-01-02*
