# PyPhotoOrganizer User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Getting Started](#getting-started)
4. [Understanding the Interface](#understanding-the-interface)
5. [Database Management](#database-management)
6. [Source Folders](#source-folders)
7. [Processing Photos](#processing-photos)
8. [Viewing Results](#viewing-results)
9. [Date Corrections](#date-corrections)
10. [Import History](#import-history)
11. [Settings](#settings)
12. [Troubleshooting](#troubleshooting)
13. [FAQ](#faq)

---

## Introduction

PyPhotoOrganizer helps you consolidate photos from multiple sources (phones, tablets, cameras, cloud backups) into a single, organized archive. It automatically:

- **Detects duplicates** using SHA-256 hashing - even if files have different names
- **Organizes by date** into Year/Month/Day folders based on when the photo was taken
- **Preserves originals** - source files are never modified
- **Tracks everything** - full audit trail of what was processed

### Key Concepts

| Term | Description |
|------|-------------|
| **Source Folder** | Where your photos currently are (phone backup, camera SD card, cloud sync folder) |
| **Archive** | Where organized, deduplicated photos are stored (your permanent photo library) |
| **Database** | Tracks all processed photos to prevent duplicates across sessions |
| **Hash** | A unique "fingerprint" of a file's contents - identical files have identical hashes |

---

## System Requirements

- **Operating System**: Windows 10/11, Linux, or macOS
- **Python**: 3.8 or higher
- **Storage**: Sufficient space for your photo archive
- **Memory**: 4GB RAM minimum (8GB+ recommended for large collections)

### Python Dependencies

```
PySide6          # GUI framework
Pillow           # Image processing
pillow-heif      # Apple HEIC format support
piexif           # EXIF metadata handling
tqdm             # Progress bars (CLI mode)
```

Install dependencies:
```bash
pip install PySide6 Pillow pillow-heif piexif tqdm
```

---

## Getting Started

### First Launch

1. **Run the application**:
   ```bash
   python main_gui.py
   ```

2. **Create your first database**:
   - A dialog appears asking you to select or create a database
   - Click "Create New Database"
   - Enter a name (e.g., "Family Photos")
   - Select your archive location (where organized photos will be stored)
   - Click "Create"

3. **Add source folders**:
   - Go to the "Setup" tab
   - Click "Add Source"
   - Browse to folders containing photos to process

4. **Start processing**:
   - Ensure checkboxes are checked for folders you want to process
   - Click "Start"

### Quick Start Workflow

```
1. Create database → 2. Add sources → 3. Click Start → 4. Review results
```

---

## Understanding the Interface

PyPhotoOrganizer uses a tabbed interface:

### Tab Overview

| Tab | Purpose |
|-----|---------|
| **Setup** | Configure source folders, start/stop processing |
| **Progress** | Real-time progress during processing |
| **Results** | Summary of completed processing |
| **Filtered Files** | Files skipped (icons, thumbnails, etc.) |
| **Logs** | Application log viewer |
| **Settings** | Organization template, filters, retention |
| **Database** | View/change current database |
| **Date Corrections** | Fix files with wrong dates |
| **Import History** | Audit trail of all import sessions |

---

## Database Management

Each database is tied to a specific archive location. You can have multiple databases for different photo collections (e.g., "Family Photos", "Work Projects", "Travel").

### Creating a New Database

1. Go to **Database** tab
2. Click "Change Database..."
3. Click "Create New Database"
4. Enter:
   - **Database Name**: Friendly name (e.g., "2024 Archive")
   - **Archive Location**: Folder where photos will be organized
   - **Video Archive** (optional): Separate location for videos
5. Click "Create"

### Switching Databases

1. Go to **Database** tab
2. Click "Change Database..."
3. Select from list of existing databases
4. Click "Select"

### Database Information

The Database tab shows:
- Database name and creation date
- Archive location
- Total photos in archive
- Last used date

---

## Source Folders

Source folders are where your unorganized photos currently reside. Common sources:
- Phone backup folders
- Camera SD card imports
- Cloud sync folders (Dropbox, Google Drive, iCloud)
- External hard drives with old photos

### Adding Source Folders

1. Go to **Setup** tab
2. Click "Add Source"
3. Browse to the folder containing photos
4. The folder appears in the source list with a checkbox

### Managing Sources

- **Enable/Disable**: Check/uncheck the box to include/exclude from processing
- **Remove**: Select folder and click "Remove Source"
- **Last Scanned**: Shows when the folder was last processed

### Source Folder Best Practices

- Add the top-level folder - subfolders are automatically included
- Don't add folders inside your archive as sources
- Keep source folders accessible during processing
- Large sources (100,000+ files) may take hours on first run

---

## Processing Photos

### Copy vs Move Mode

| Mode | Behavior | When to Use |
|------|----------|-------------|
| **Copy** (default) | Leaves source files intact | First-time imports, testing |
| **Move** | Deletes source after successful copy | Cleaning up after verification |

**Warning**: Move mode permanently deletes source files after copying. Only use after verifying your archive is correct.

### Starting Processing

1. Go to **Setup** tab
2. Check boxes for source folders to process
3. Select Copy or Move mode
4. Click "Start"

### During Processing

The **Progress** tab shows:
- Current stage (Scanning, Processing, Organizing)
- Files processed / total files
- Current file being processed
- Time elapsed and estimated remaining

### Stopping Processing

Click "Stop" to halt processing. Progress is saved to the database, so you can resume later by running again - already processed files will be skipped.

### What Happens During Processing

1. **Scanning**: Finds all photo/video files in source folders
2. **Filtering**: Removes non-photos (icons, thumbnails, web graphics)
3. **Hashing**: Calculates unique fingerprint for each file
4. **Duplicate Detection**: Compares against database of known files
5. **Organizing**: Copies unique files to archive in date-based folders

---

## Viewing Results

After processing completes, the **Results** tab shows:

### Statistics

- **Total Files Examined**: All files found in source folders
- **New Originals**: Unique files copied to archive
- **Duplicates Found**: Files already in your archive
- **Filtered**: Non-photo files (icons, thumbnails)
- **Unreliable Dates**: Files needing date correction

### Filtered Files Tab

Shows files that were skipped with reasons:
- Too small (under 50KB)
- Too small dimensions (under 800x600)
- Icon/thumbnail patterns in filename
- Small square images (likely icons)

### Archive Structure

Files are organized into:
```
Archive/
├── 2024/
│   ├── 01/
│   │   ├── 15/
│   │   │   ├── IMG_1234.jpg
│   │   │   └── vacation_photo.jpg
│   │   └── 16/
│   └── 02/
└── 2023/
```

The exact structure depends on your organization template (see Settings).

---

## Date Corrections

Some photos have unreliable dates:
- Scanned photos (scanner assigns scan date, not photo date)
- Files with corrupted or missing EXIF data
- Photos from old cameras with wrong date settings

### Viewing Flagged Files

1. Go to **Date Corrections** tab
2. Files are listed with:
   - Original detected date
   - Flag reason (no_exif, suspicious, user_specified)
   - Current status (Pending, Corrected, Reorganized)

### Correcting a Single File

1. Click on file in the grid
2. Preview shows the image
3. Click "Correct Date..."
4. Enter the correct date
5. Options:
   - **Write EXIF**: Updates EXIF data in archive file
   - **Mark for Reorganization**: File will be moved to correct date folder
6. Click "Apply"

### Batch Corrections

For multiple files from the same event:

1. Select multiple files (Shift+Click or Ctrl+Click)
2. Click "Batch Correct"
3. Choose mode:
   - **Same Date**: All files get the same date
   - **Sequential**: Dates increment by 1 day per file
4. Enter starting date
5. Click "Apply"

### Reorganization

After correcting dates:

1. Click "Reorganize All Marked"
2. Confirm the operation
3. Files are moved to correct date-based folders
4. Empty source folders are cleaned up

### Managing Unreliable Paths

If you have folders that always have wrong dates (e.g., scanned photos):

1. Click "Manage Unreliable Paths..."
2. Add folder paths
3. Future imports from these paths are automatically flagged

---

## Import History

The **Import History** tab provides a complete audit trail of all processing sessions.

### Viewing Sessions

- Session list shows date, status, and file counts
- Filter by status (All, Completed, Failed, Cancelled)
- Click a session to view details

### Session Details

- Start/end time and duration
- Files processed, duplicates found, errors
- Configuration used (source folders, modes)

### File-Level Details

Three tabs show file operations:
- **All Files**: Every file processed
- **Duplicates**: Only duplicate files with original locations
- **Errors**: Failed operations with error messages

### Exporting Reports

- **Export JSON**: Full session data for external analysis
- **Export CSV**: Spreadsheet-compatible format
- **Export Duplicates**: List of all duplicate relationships

### Retention Settings

Control how long history is kept (in Settings tab):
- **Keep All**: Never delete (may grow large)
- **Keep Last N Sessions**: Delete older sessions
- **Keep Last N Days**: Time-based cleanup

---

## Settings

The **Settings** tab controls how photos are organized and filtered.

### Organization Template

Controls folder structure in archive:

| Template | Result |
|----------|--------|
| `{year}/{month}/{day}` | 2024/01/15/ |
| `{year}/{month}` | 2024/01/ |
| `{year}` | 2024/ |

### Photo Filter Settings

Controls which files are considered "real photos":

| Setting | Default | Purpose |
|---------|---------|---------|
| Min File Size | 50 KB | Skip tiny files |
| Min Dimensions | 800x600 | Skip small images |
| Max Dimensions | 50000x50000 | Skip oversized images |
| Small Square Filter | 400px | Skip square icons |

### File Renaming (Optional)

Enable to rename files during import:

| Template | Example Result |
|----------|----------------|
| `{year}{month}{day}_{original_name}` | 20240115_IMG_1234.jpg |
| `{year}-{month}-{day}_{counter:04d}` | 2024-01-15_0001.jpg |

### Retention Settings

For Import History cleanup:
- Retention mode (sessions, days, or keep all)
- Count or days to keep
- Auto-cleanup on startup option

---

## Troubleshooting

### Common Issues

#### "No database selected"
- Go to Database tab and select or create a database

#### Processing is slow
- First run indexes all files - subsequent runs are faster
- Large video files take longer to hash
- Network drives are slower than local storage

#### Duplicate not detected
- File must be byte-for-byte identical
- Different resolution = different file = not duplicate
- Edited photos are not duplicates of originals

#### Wrong date in archive
- Use Date Corrections tab to fix
- Set up Unreliable Paths for known problematic sources

#### Application won't start
- Check Python version (3.8+)
- Verify all dependencies installed
- Check log files for errors

### Log Files

Log files are in the application directory:
- `main_app_error.log`
- `DuplicateFileDetection_app_error.log`
- `photo_filter.log`

Logs rotate automatically at 5MB (keeps 3 backups).

To clear old logs:
```bash
rm *.log *.log.*
```

### Performance Tips

1. **Use SSDs** for archive storage when possible
2. **Process locally** - network drives are much slower
3. **Start with Copy mode** - verify before using Move
4. **Process in batches** - don't add 500,000 files at once
5. **Close other applications** during large imports

---

## FAQ

### Q: Are my source files modified?
**A:** No. Source files are never modified. Only archive copies receive EXIF updates during date corrections.

### Q: What if I accidentally delete the database?
**A:** Your photos in the archive are safe. You'll lose duplicate detection history, so re-importing may create duplicates.

### Q: Can I use network drives?
**A:** Yes, but processing is slower. Local SSDs are recommended for best performance.

### Q: What file types are supported?
**A:**
- Photos: JPG, JPEG, PNG, TIFF, HEIC, HEIF
- Videos: MP4, MOV, AVI, MKV

### Q: How long does processing take?
**A:** Varies by:
- Number of files (1000 files/minute typical)
- File sizes (videos take longer)
- Storage speed (SSD vs HDD vs network)
- First run vs subsequent (hashes cached)

### Q: Can I run multiple instances?
**A:** Not recommended with the same database. Use separate databases for parallel processing.

### Q: What happens if processing is interrupted?
**A:** Progress is saved. Simply run again - already processed files are skipped automatically.

### Q: How do I back up my database?
**A:** Copy the `.db` file to a safe location. The archive folder should also be backed up separately.

### Q: Can I change the archive location?
**A:** Each database is bound to its archive location. Create a new database for a different location, or manually move files and update paths.

### Q: Why are some photos marked "suspicious date"?
**A:** Dates before 1990, after next year, or exactly 1970-01-01 are flagged as likely incorrect.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+Q | Quit application |
| Shift+Click | Select range of files |
| Ctrl+Click | Toggle file selection |
| Double-click | Toggle checkbox in grids |

---

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Log Files**: Include relevant log excerpts when reporting issues
- **Screenshots**: Help illustrate UI-related problems

---

## Version History

| Version | Key Features |
|---------|--------------|
| 2.0 | GUI interface, database-per-archive model |
| 2.1 | Persistent source directories |
| 2.2 | Date correction system |
| 2.2.2 | File renaming templates |
| 2.2.3 | Hash history for EXIF edits |
| 2.3 | Import audit system |
| 2.3.1 | Log rotation |

---

*PyPhotoOrganizer - Organize your memories, eliminate duplicates.*
