# PyPhotoOrganizer User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Getting Started](#getting-started)
4. [Understanding the Interface](#understanding-the-interface)
5. [Database Management](#database-management)
6. [Database Health and Recovery](#database-health-and-recovery)
7. [Source Folders](#source-folders)
8. [Album Association for Source Folders](#album-association-for-source-folders)
9. [Processing Photos](#processing-photos)
10. [How the System Determines Photo Date](#how-the-system-determines-photo-date)
11. [Import History](#import-history)
12. [Photo Review App](#photo-review-app)
13. [Date Corrections (in Photo Review App)](#date-corrections)
14. [File Version Management](#file-version-management)
15. [Prior Revision Archive System](#prior-revision-archive-system)
16. [Archive Change Detection](#archive-change-detection)
17. [Bulk Delete Matching Files](#bulk-delete-matching-files)
18. [Delete Vault and File Recovery](#delete-vault-and-file-recovery)
19. [Cloud Storage](#cloud-storage)
20. [Auto-Import Service](#auto-import-service)
21. [Settings](#settings)
22. [Troubleshooting](#troubleshooting)
23. [Recovering from Data or Storage Corruption](#recovering-from-data-or-storage-corruption)
24. [FAQ](#faq)

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

**Required:**
```
PySide6          # GUI framework
Pillow           # Image processing
pillow-heif      # Apple HEIC format support
piexif           # EXIF metadata handling
tqdm             # Progress bars (CLI mode)
```

**Optional (for cloud storage):**
```
boto3            # Amazon S3 support
```

Install required dependencies:
```bash
pip install PySide6 Pillow pillow-heif piexif tqdm
```

Install with cloud storage support:
```bash
pip install PySide6 Pillow pillow-heif piexif tqdm boto3
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

PyPhotoOrganizer consists of two applications:
- **main_gui** (main_gui.py) - For archive setup and import management
- **Photo Review** (photo_review_app.py) - For browsing, reviewing, and correcting photos

### Main GUI Tab Overview

| Tab | Purpose |
|-----|---------|
| **Import Settings** | Configure source folders, filtering, start/stop processing |
| **Archive Settings** | Organization templates, file renaming |
| **System Settings** | Database info, operation mode, performance |
| **Progress** | Real-time progress during processing |
| **Import History** | Complete accounting of all imports (new, duplicates, filtered, errors) |
| **Logs** | Application log viewer |

### Photo Review App

For reviewing imported photos, correcting dates, rotating images, and deleting unwanted files, use the separate **Photo Review** application:

```bash
python photo_review_app.py
```

The Photo Review app provides:
- Grid-based photo browsing with thumbnail view
- Search and filter capabilities
- **Date corrections** with unreliable date filters
- **Reorganization** of corrected files (Actions menu or right-click → Reorganize Marked Files)
- **Unreliable paths management** (Actions menu → Manage Unreliable Paths)
- Image rotation with version history
- File deletion with restore capability
- Visual status indicators (unreliable/corrected/reorganized/has revisions)
- **Fixed bottom action bar** with Delete, Rotate, Fix Date, Deselect All buttons (always visible)
- **Right-click context menu** for quick access to all actions

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

## Database Health and Recovery

PyPhotoOrganizer includes comprehensive data protection features to safeguard your photo database against corruption, crashes, and other issues.

### Automatic Health Checks

When you open a database, the application automatically runs health checks to detect potential problems:

| Check | What It Detects |
|-------|-----------------|
| **Integrity Check** | Database file corruption |
| **Pending Operations** | Interrupted imports from crashes |
| **WAL Size** | Large write-ahead log files |
| **Queued Audits** | Failed audit entries awaiting retry |

**What Happens:**
- **Critical Issues**: If database corruption is detected, you'll see an error dialog with recovery options
- **Pending Operations**: If a previous import was interrupted, you'll be offered the chance to recover
- **Warnings**: Non-critical issues (like large WAL files) are shown as warnings

### Automatic Backups (Quick Snapshots)

The application automatically creates database backups before major operations:

**When Backups Are Created:**
- Before starting an import
- Before batch operations (future enhancement)

**Backup Location:** `<database_directory>/db_snapshots/`

**Retention:** The last 5 snapshots are kept automatically. Older backups are deleted to save space.

**Backup Files:** Named like `db_snapshot_20240115_143022_pre_import_a1b2c3d4.db`

### Crash Recovery

If the application crashes or loses power during an import, PyPhotoOrganizer can recover:

**On Next Startup:**
1. System detects incomplete operations
2. You're shown a recovery dialog:
   - **Recover**: Attempt to complete or clean up interrupted operations
   - **Discard**: Remove all pending operation records

**What Recovery Does:**
- **Verified copies**: Files that were copied and verified are marked complete
- **Unverified copies**: Files are re-verified; corrupt copies are deleted
- **Partial operations**: Incomplete files are cleaned up
- **Database records**: All tracking records are properly resolved

**After Recovery:**
- You can re-run the import to process any files that were skipped
- Already-processed files are detected as duplicates and skipped automatically

### Copy Verification

Every file copied to your archive is verified after the copy operation:

1. **File is copied** from source to archive
2. **Hash is recalculated** on the destination file
3. **Hashes are compared** to detect corruption
4. **Corrupt copies are removed** automatically

This ensures that network glitches, disk errors, or other issues don't result in corrupted photos in your archive.

### Restoring a Corrupt Database

If your database becomes corrupted or you need to restore from a backup:

#### Method 1: Restore from Quick Snapshot (Recommended)

Quick snapshots are stored in the `db_snapshots` folder next to your database.

**Steps:**

1. **Close PyPhotoOrganizer** completely

2. **Find your database location**:
   - Open the application's settings or check where your `.db` file is stored
   - Look for a folder called `db_snapshots` in the same directory

3. **List available snapshots**:
   ```
   db_snapshots/
   ├── db_snapshot_20240115_143022_pre_import_a1b2c3d4.db
   ├── db_snapshot_20240114_091533_pre_import_e5f6g7h8.db
   └── db_snapshot_20240113_162045_pre_import_i9j0k1l2.db
   ```
   Files are named by date/time, so choose the most recent one from before the corruption.

4. **Backup your current (corrupted) database**:
   ```bash
   # Linux/macOS
   cp PhotoDB.db PhotoDB_corrupted_backup.db

   # Windows (Command Prompt)
   copy PhotoDB.db PhotoDB_corrupted_backup.db
   ```

5. **Restore from snapshot**:
   ```bash
   # Linux/macOS
   cp db_snapshots/db_snapshot_20240115_143022_pre_import_a1b2c3d4.db PhotoDB.db

   # Windows (Command Prompt)
   copy db_snapshots\db_snapshot_20240115_143022_pre_import_a1b2c3d4.db PhotoDB.db
   ```

6. **Restart PyPhotoOrganizer** and verify the database loads correctly

7. **Re-run import** if needed - any files imported after the snapshot will be detected and re-imported

#### Method 2: Restore from External Backup

If you've created manual backups of your database file:

1. **Close PyPhotoOrganizer**
2. **Replace the database file** with your backup copy
3. **Also restore associated files** if present:
   - `PhotoDB.db-wal` (Write-Ahead Log)
   - `PhotoDB.db-shm` (Shared Memory file)
4. **Restart the application**

#### Method 3: Create a New Database

If no backup is available and the database is unrecoverable:

1. **Close PyPhotoOrganizer**
2. **Rename the corrupted database** (don't delete it yet):
   ```bash
   mv PhotoDB.db PhotoDB_corrupted.db
   ```
3. **Start PyPhotoOrganizer** - it will prompt you to create or select a database
4. **Create a new database** with the same archive location
5. **Re-scan your archive** to rebuild the database:
   - The application will hash all existing archive files
   - File metadata will be rebuilt from EXIF data
   - Duplicate detection will resume working

**What You Lose:**
- Import history and audit trails
- Unreliable date flags (you'll need to re-identify them)
- Album associations and configurations
- Source directory settings

**What You Keep:**
- All photos in your archive (files are not affected)
- Folder organization
- File content (EXIF data, pixel content)

### Preventing Database Corruption

**Best Practices:**

1. **Don't force-quit** the application during imports - use the Stop button instead
2. **Use reliable storage** - avoid network drives with poor connections
3. **Keep backups** - periodically copy your `.db` file to a safe location
4. **Monitor disk space** - full disks can cause corruption
5. **Use UPS** - power loss during writes can corrupt databases

**The application helps by:**
- Checkpointing the WAL file before backups
- Using SQLite's WAL mode for crash resilience
- Verifying copies after every file transfer
- Creating automatic snapshots before imports

### Viewing Database Health Status

Currently, health checks run automatically on startup. You can see:
- **Startup dialogs** for any detected issues
- **Log files** for detailed health check results

Future versions will include a dedicated Database Health panel in the UI.

### Understanding Health Warnings

| Warning | Meaning | Action |
|---------|---------|--------|
| "X operations need recovery" | Previous import was interrupted | Choose Recover or Discard |
| "Large WAL file (X MB)" | Write-ahead log is unusually large | Usually resolves automatically; restart app if persistent |
| "X failed audit entries pending" | Some tracking records couldn't be saved | Processed automatically on startup |

### Technical Details

**Quick Backup Process:**
1. WAL checkpoint is performed (consolidates pending writes)
2. Database file is copied to snapshots directory
3. Backup is recorded in QuickBackups table
4. Old backups beyond retention limit are deleted

**Crash Recovery Process:**
1. PendingOperations table is scanned for incomplete operations
2. Each operation is evaluated based on its status:
   - `pending`: Operation never started - clean up record
   - `copied`: File was copied - verify integrity
   - `verified`: Copy verified - ready for database commit
   - `failed`: Operation failed - clean up orphaned files
3. Corrupt or orphaned files in archive are removed
4. Database records are cleaned up
5. User is informed of recovery results

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

## Album Association for Source Folders

You can associate an album with each source folder to automatically add imported photos to that album. This is perfect for:

- **Phone backups**: All photos from your phone automatically go to a "Phone Photos" album
- **Camera imports**: SD card imports go to a "Camera" album
- **Photo frame folders**: Automatically populate albums that sync to digital photo frames
- **Family collections**: Different family members' photos go to separate albums

### Setting Up Album Association

1. Go to **Import Settings** tab
2. In the source folder table, find the **Album** column
3. Click the dropdown and select an album, or choose **"+ New Album..."** to create one

### Creating a New Album

When you select **"+ New Album..."** from the dropdown:

1. **Album Name**: Enter a descriptive name (e.g., "Phone Photos", "2024 Vacation")
2. **Storage Location**: Browse to select where album copies will be stored
   - This is separate from your main archive
   - Ideal for folders that sync to photo frames or cloud services
3. **Description**: Optional notes about the album
4. **Sync Deletions**: When checked, photos removed from archive are also removed from album
5. Click **OK** to create the album

### Sub-Albums for Subdirectories

Enable the **Sub-Albums** checkbox to automatically create sub-albums based on your source folder structure.

**Example**: If your phone backup has this structure:
```
/Phone/
├── Camera/
│   └── photo1.jpg
├── Screenshots/
│   └── screenshot1.png
└── WhatsApp/
    └── Media/
        └── image1.jpg
```

With "Phone Photos" album and Sub-Albums enabled, you get:
- "Phone Photos - Camera" album (contains photo1.jpg)
- "Phone Photos - Screenshots" album (contains screenshot1.png)
- "Phone Photos - WhatsApp - Media" album (contains image1.jpg)

**Sub-Album Storage**: Sub-albums are stored in subfolders of the parent album's location:
```
/Albums/Phone Photos/
├── Camera/
│   └── photo1.jpg
├── Screenshots/
│   └── screenshot1.png
└── WhatsApp/
    └── Media/
        └── image1.jpg
```

### How It Works

During import:

1. Photos are first copied to your main archive (as always)
2. If the source folder has an album association:
   - A copy is also added to the album's storage location
   - If sub-albums are enabled, the appropriate sub-album is used
   - New sub-albums are created automatically when needed
3. The import summary shows how many files were added to albums

### Important Notes

- **Files are copied twice**: Once to archive, once to album storage
- **Album failures don't stop import**: If album storage is unavailable, archive import continues
- **Albums are separate from archive**: Deleting from archive optionally removes from albums (sync_deletions)
- **Sub-Albums checkbox**: Only enabled when an album is selected
- **Settings persist**: Album associations are saved and restored when you restart the application

### Best Practices

1. **Use fast storage for albums**: Album storage can be on slower drives since it's secondary
2. **Consider sync_deletions carefully**: Disable if album is your only backup
3. **Organize by device/source**: Associate each device's backup folder with its own album
4. **Use sub-albums for complex sources**: Great for phones with many app folders

---

## Content-Based Duplicate Detection

**NEW in v3.3** - PyPhotoOrganizer now includes content-based (pixel) hashing to detect visually identical images even when their metadata differs.

### What is Content-Based Hashing?

Traditional file hashing (SHA-256) detects exact byte-for-byte duplicates. However, two photos can be visually identical but have different file hashes due to:
- Different EXIF metadata (edited dates, software tags)
- Re-saved with slightly different compression
- Stripped or modified metadata

Content-based hashing solves this by hashing the actual pixel data, ignoring metadata.

### How It Works

1. **Algorithm**: SHA-256 hash of normalized RGB pixel bytes
2. **EXIF Handling**: Images are auto-rotated using EXIF orientation before hashing
3. **Normalization**: All images converted to RGB mode for consistent comparison
4. **Videos**: Videos are skipped (only images are content-hashed)

### During Import

When content hashing is enabled:
1. Files are first checked for exact file duplicates (fast)
2. Unique files then have their content hash calculated
3. If content hash matches an existing file, it's flagged as a "content duplicate"
4. Content duplicates appear with purple highlighting in Import History

### Viewing Content Duplicates

**Import History Tab:**
- Use the "Show" dropdown and select "Content Duplicates"
- Content duplicates are highlighted in purple (#9966CC)

**Photo Review App:**
- Use the View filter dropdown in the toolbar
- Select "Content Duplicates" to see all files with matching pixel content
- Files are grouped by their content hash

### Backfilling Existing Archives

For archives created before content hashing was available:

1. Go to **System Settings** tab
2. Find the "Content-Based Duplicate Detection" section
3. Click **"Calculate Content Hashes for Existing Files"**
4. Progress bar shows backfill status
5. Click **"Cancel"** to stop if needed

**What the backfill does:**
- Scans all image files without content hashes
- Calculates and stores content hash for each
- Detects newly discovered duplicates (same content, different files)
- Reports statistics when complete

### Enable/Disable Content Hashing

Content hashing is enabled by default. To toggle:

1. Go to **System Settings** tab
2. Find "Content-Based Duplicate Detection" section
3. Check/uncheck **"Enable content-based duplicate detection"**

**Performance Note:** Content hashing adds processing time during imports (must decode and hash each image's pixels). For large imports, you may want to disable it temporarily.

### Content Hash Test Tool

A standalone GUI tool is available for testing content hashing:

```bash
python tests/content_hash_test_gui.py
```

Features:
- Select any folder to scan for images
- View content hashes for all files
- Identify duplicates (highlighted with colors)
- Export results (TXT, CSV, JSON)

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
5. **Date Extraction**: Determines when each photo was originally taken
6. **Organizing**: Copies unique files to archive in date-based folders

---

## How the System Determines Photo Date

One of PyPhotoOrganizer's most important functions is determining **when a photo was originally taken**. This date is used to organize your photos into Year/Month/Day folders. Getting this right is crucial for a well-organized archive.

### Why Date Detection Matters

When you copy photos from different sources (phones, cameras, cloud backups), the operating system often assigns new file dates:

| Scenario | OS File Date | Actual Photo Date |
|----------|--------------|-------------------|
| Copy from phone to computer | Today's date | Date photo was taken |
| Download from cloud backup | Download date | Original capture date |
| Restore from backup | Restore date | Original capture date |
| Receive via email/messaging | Date received | Date photo was taken |

If we only used OS file dates, your photos would be organized by when you *copied* them, not when you *took* them. PyPhotoOrganizer solves this by reading the **embedded metadata** in each file.

### Date Sources (In Priority Order)

#### For Photos (Images)

The system reads dates from multiple embedded metadata sources and uses an intelligent algorithm to select the most accurate one:

| Priority | Source | Description | Reliability |
|----------|--------|-------------|-------------|
| 1 | **EXIF DateTimeOriginal** | When the camera shutter clicked | Highest |
| 2 | **EXIF DateTimeDigitized** | When the image was digitized | High |
| 3 | **EXIF GPS DateTime** | GPS timestamp (UTC) | High |
| 4 | **EXIF DateTime** | File modification time in EXIF | Medium |
| 5 | **EXIF PreviewDateTime** | When preview was generated | Low |
| 6 | **IPTC Date Created** | Publishing/editorial date | Medium |
| 7 | **XMP CreateDate** | XMP metadata date | Medium |
| 8 | **Filename Date** | Date extracted from filename pattern | Medium |
| 9 | **Path Date** | Date from folder structure | Low-Medium |
| 10 | **OS File Metadata** | Operating system timestamps | Low |
| 11 | **Year 1000 Fallback** | Indicates no date found | None |

**The Selection Algorithm:**

1. If **DateTimeOriginal** exists and is valid, use it (this is the most authoritative source - it's when the shutter actually clicked)

2. If DateTimeOriginal is missing, the system uses the **earliest valid date** among the remaining EXIF fields

   *Why earliest?* A photo can only be modified *after* it was created. If a file shows DateTime as 2021 but DateTimeDigitized as 2013, the 2013 date is more likely to be the original capture date.

3. If no valid EXIF dates exist, try IPTC and XMP metadata

4. If no embedded metadata exists, try extracting date from the **filename** (see below)

5. If filename has no date, try extracting from the **folder path**

6. If all else fails, fall back to OS file timestamps

#### For Videos

Videos don't have EXIF data, so the system uses different sources:

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | **ffprobe** | `creation_time` tag from video metadata |
| 2 | **mutagen** | `©day` tag for MP4/MOV files |
| 3 | **QuickTime atoms** | Direct reading of `mvhd` atom |
| 4 | **Filename Date** | Date extracted from filename pattern |
| 5 | **Path Date** | Date from folder structure |
| 6 | **OS File Metadata** | Operating system timestamps |
| 7 | **Year 1000 Fallback** | Indicates no date found |

### Filename Date Extraction

When a file has no embedded metadata, the system can extract dates from common filename patterns. This is especially useful for:
- Screenshots (which rarely have EXIF data)
- WhatsApp images
- Files exported from apps that strip metadata
- Renamed files with date prefixes

**Supported Filename Patterns:**

| Pattern | Example | What It Extracts |
|---------|---------|------------------|
| `IMG_YYYYMMDD_HHMMSS` | `IMG_20230415_123456.jpg` | Full date and time |
| `VID_YYYYMMDD_HHMMSS` | `VID_20230415_123456.mp4` | Full date and time |
| `PXL_YYYYMMDD_HHMMSS` | `PXL_20230415_123456.jpg` | Full date and time (Pixel phones) |
| `Screenshot_YYYYMMDD-HHMMSS` | `Screenshot_20230415-123456.png` | Full date and time |
| `YYYY-MM-DD at HH.MM.SS` | `Photo 2023-04-15 at 12.34.56.jpg` | Full date and time (iOS sharing) |
| `IMG-YYYYMMDD-WA` | `IMG-20230415-WA0001.jpg` | Date only (WhatsApp) |
| `YYYY-MM-DD` | `2023-04-15_vacation.jpg` | Date only |
| `YYYYMMDD` | `20230415.jpg` | Date only |

**Example:**
```
File: Screenshot_20231225-143022.png
Metadata: (none - screenshots don't have EXIF)
Filename: Contains date pattern

Result: Uses 2023-12-25 14:30:22 from filename
Archived to: 2023/12Dec/25/
```

### Path Date Extraction

If the filename has no date, the system checks the folder structure. This works well when photos are already organized into date folders:

| Pattern | Example | What It Extracts |
|---------|---------|------------------|
| `/YYYY/MM/DD/` | `/Photos/2023/04/15/photo.jpg` | Full date |
| `/YYYY-MM-DD/` | `/Archive/2023-04-15/photo.jpg` | Full date |
| `/YYYY/MM/` | `/Photos/2023/04/photo.jpg` | Year and month (day=1) |
| `/YYYY-MM/` | `/Archive/2023-04/photo.jpg` | Year and month (day=1) |
| `/YYYY/` | `/Photos/2023/photo.jpg` | Year only (month=1, day=1) |

**Note:** Path dates are less reliable than filename dates because:
- The path may represent when photos were *organized*, not *taken*
- Year-only paths provide incomplete information

**Example:**
```
File: /Photos/2023/04/15/vacation_beach.jpg
Metadata: (none)
Filename: vacation_beach.jpg (no date)
Path: /2023/04/15/

Result: Uses 2023-04-15 from path
Archived to: 2023/04Apr/15/
Status: Flagged for review (date from path)
```

### Understanding EXIF Date Fields

Digital cameras and phones store multiple date fields in EXIF metadata:

| Field | What It Records | When It Changes |
|-------|-----------------|-----------------|
| **DateTimeOriginal** | When you pressed the shutter button | Never (unless EXIF is edited) |
| **DateTimeDigitized** | When the image was digitized | Same as Original for digital cameras; different for scans |
| **DateTime** | Last modification time | Updated when photo is edited |
| **GPSDateTime** | GPS timestamp when photo was taken | Requires location services enabled |
| **PreviewDateTime** | When thumbnail/preview was created | When software regenerates preview |

**Example**: You take a photo on December 14, 2013, then edit it on June 15, 2021:
- DateTimeOriginal: 2013-12-14 17:05:19 (unchanged)
- DateTime: 2021-06-15 10:30:00 (updated by editing software)

The system correctly identifies 2013-12-14 as the original date.

### Date Validation

Not all dates found in files are trustworthy. The system validates each date:

| Check | Reason |
|-------|--------|
| **Year 1990-present** | Consumer digital cameras didn't exist before ~1990 |
| **Not future dates** | Year > current+1 indicates clock error |
| **Not Unix epoch** | 1970-01-01 00:00:00 indicates unset date |
| **Not null date** | 0000-00-00 00:00:00 indicates missing data |
| **Parseable format** | Must match `YYYY:MM:DD HH:MM:SS` format |

### When Dates Are Flagged as Unreliable

Some photos are flagged for manual review because their dates may be incorrect:

| Flag Reason | What It Means | Common Causes |
|-------------|---------------|---------------|
| **no_exif** | No EXIF metadata found | Screenshots, web images, very old digital photos |
| **suspicious** | Date fails validation | Camera clock was wrong, corrupted metadata |
| **year_1000** | Complete failure to find date | Heavily processed images, unusual formats |
| **user_specified** | File is in a path you marked as unreliable | Scanned photos, downloaded images |

Flagged files appear in the **Photo Review** app where you can manually correct dates.

### Common Scenarios

#### Scenario 1: Photo with Complete Metadata
```
File: IMG_1234.jpg
EXIF DateTimeOriginal: 2019-07-04 14:30:22
EXIF DateTimeDigitized: 2019-07-04 14:30:22
EXIF DateTime: 2019-07-04 14:30:22
OS Modified: 2024-01-15 09:00:00

Result: Uses 2019-07-04 (DateTimeOriginal)
Archived to: 2019/07Jul/04/
```

#### Scenario 2: Edited Photo (DateTime Updated)
```
File: vacation_edited.jpg
EXIF DateTimeOriginal: 2018-08-15 10:45:00
EXIF DateTime: 2023-03-20 16:00:00 (when you edited it)
OS Modified: 2024-01-15 09:00:00

Result: Uses 2018-08-15 (DateTimeOriginal takes priority)
Archived to: 2018/08Aug/15/
```

#### Scenario 3: No DateTimeOriginal
```
File: old_camera_photo.jpg
EXIF DateTimeOriginal: (missing)
EXIF DateTimeDigitized: 2005-12-25 08:30:00
EXIF DateTime: 2010-06-01 12:00:00
OS Modified: 2024-01-15 09:00:00

Result: Uses 2005-12-25 (earliest EXIF date)
Archived to: 2005/12Dec/25/
```

#### Scenario 4: No EXIF Data
```
File: screenshot.png
EXIF: (none)
IPTC: (none)
OS Created: 2024-01-10 15:30:00
OS Modified: 2024-01-10 15:30:00

Result: Uses 2024-01-10 (OS metadata), flagged as unreliable
Archived to: 2024/01Jan/10/
Status: Flagged for review (no_exif)
```

#### Scenario 5: Scanned Photo
```
File: grandma_1965.jpg
EXIF DateTimeOriginal: 2023-11-15 14:00:00 (scan date!)
OS Modified: 2023-11-15 14:00:00

Result: Uses 2023-11-15 (only date available)
Archived to: 2023/11Nov/15/
Recommendation: Manually correct to actual photo date
```

### Viewing Date Source Information

After import, you can see which date source was used for each file:

1. **Import History Tab**: Shows date source in file details
2. **Photo Review App**: Preview panel shows "Detected Date" with source
3. **Database**: `date_source` field records: `exif`, `exif_digitized`, `exif_gps`, `exif_datetime`, `iptc`, `xmp`, `video_metadata`, `filename`, `path_ymd`, `path_ym`, `path_y`, `os_metadata`, or `fallback`

### Tips for Best Results

1. **Preserve EXIF data**: When editing photos, use software that preserves original EXIF metadata

2. **Set camera clocks correctly**: Ensure your camera/phone has the correct date and time

3. **Review flagged files**: After import, check files flagged as unreliable in Photo Review

4. **Mark known-unreliable folders**: Use the source folder settings to mark folders containing scans or downloads as "unreliable dates"

5. **Don't strip metadata**: Avoid tools that remove EXIF data when sharing photos

---

## Import History

After processing completes, the **Import History** tab shows complete accounting of all operations:

### Statistics Row

- **Total Scanned**: All files found in source folders
- **Processed**: Files that were evaluated
- **New Files**: Unique files copied to archive
- **Duplicates**: Files already in your archive
- **Filtered**: Non-photo files (icons, thumbnails, web graphics)
- **Errors**: Files that encountered processing errors

### File Categories

Use the "Show" dropdown to filter the file list:
- **All Files**: Complete list of all operations
- **New Files (Added to Archive)**: Successfully imported photos
- **Duplicates**: Files that matched existing archive photos
- **Content Duplicates**: Files with matching pixel content (different metadata)
- **Filtered (Icons/Thumbnails)**: Files skipped by photo filter with reasons:
  - Too small (under 50KB)
  - Too small dimensions (under 800x600)
  - Icon/thumbnail patterns in filename
  - Small square images (likely icons)
- **Recently Overridden**: Files imported via Override Skip feature
- **External Modifications**: Files detected as externally modified by Archive Change Detection
- **Bulk Delete Operations**: Files processed by bulk delete matching:
  - `bulk_delete_matched` (success): Archive file deleted successfully
  - `bulk_delete_matched` (failed): Deletion failed
  - `bulk_delete_not_found` (skipped): Reference file not in archive
- **Errors**: Files that failed processing

### Preview and Details

Double-click any file row to open the **Detachable Preview Window** with:
- Large zoomable image preview
- File information (size, modified date)
- Image properties (dimensions, format)
- EXIF data (camera, date taken, exposure settings)
- Revision history

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

> **Note**: Date corrections are now handled in the **Photo Review** application.
> Launch it with: `python photo_review_app.py`

Some photos have unreliable dates:
- Scanned photos (scanner assigns scan date, not photo date)
- Files with corrupted or missing EXIF data
- Photos from old cameras with wrong date settings

### Viewing Files with Unreliable Dates

1. Launch **Photo Review** app
2. Use the Query Builder to filter for files with unreliable dates
3. Files are listed with:
   - Original detected date
   - Flag reason (no_exif, suspicious, user_specified)
   - Current status (Pending, Corrected, Reorganized)

### Using the Preview Panel

When you select a file, the **Preview Panel** opens with detailed information and actions:

**Image Preview:**
- Large zoomable image viewer
- **Rubber band zoom**: Click and drag to zoom into a region
- **Reset zoom**: Double-click anywhere to fit image to view
- Shows rotated/modified version (from archive) when available

**File Details Panel** (left side):
- **Source**: Original file location (never modified)
- **Archive**: Current location in your archive
- **Detected Date**: Date extracted during import (with source: EXIF, OS, fallback)
- **Corrected Date**: Your corrected date (if set)
- **Flag Reason**: Why file was flagged (No Exif, Year 1000, Suspicious, User Specified)
- **Status**: Pending, Corrected, or Reorganized
- **Hash**: SHA-256 hash (click to copy)

**Source File Actions:**
- **Open Source File**: Opens original file with system default application
- **Open Source Folder**: Opens folder containing source file in file manager
- **Copy Source Path**: Copies source path to clipboard

**Archive File Actions:**
- **Open Archive File**: Opens archive file with system default application
- **Open Archive Folder**: Opens folder containing archive file in file manager
- **Copy Archive Path**: Copies archive path to clipboard

**Revisions Panel** (right side):
- Shows complete version history of the file
- Lists: original import, rotations, date corrections
- Each entry shows: version number, modification type, timestamp
- Current version marked with **[CURRENT]**
- Missing files shown in gray with "(missing)"
- **Double-click** a revision to:
  - **Preview in new window**: Opens secondary preview without leaving current file
  - **Open with system viewer**: Launches file in your default image application

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

After correcting dates, files need to be moved to their correct date-based folders:

**Using the Actions Menu:**
1. Go to **Actions** menu → **Reorganize Marked Files** (or press **Ctrl+M**)
2. Review the count of files to be reorganized
3. Confirm the operation
4. Progress dialog shows each file being processed
5. Files are moved to correct date-based folders
6. Empty source folders are cleaned up
7. Database is updated with new file locations

### Managing Unreliable Paths

If you have folders that always have wrong dates (e.g., scanned photos):

**Using the Actions Menu:**
1. Go to **Actions** menu → **Manage Unreliable Paths...**
2. Add folder paths (e.g., `/mnt/scans/family_photos/`)
3. Click "Add Path" for each folder
4. Future imports from these paths are automatically flagged for review

---

## File Version Management

**NEW in v2.4** - PyPhotoOrganizer can now track multiple variations of the same photo (rotated, cropped, color-corrected) while preventing duplicates. This is especially useful when you've edited photos externally and want to re-import them without creating duplicates.

### Understanding File Versions

When you modify a photo (rotation, crop, color adjustment), the file's content changes, which changes its hash. Without version management, re-importing the modified file would create a duplicate. With version management:

- ✅ All versions are **linked to the original photo**
- ✅ Any version is **detected as a duplicate** during import
- ✅ Version history is **preserved** for reference
- ✅ You can **restore previous versions** if needed

### How It Works

**Behind the Scenes:**

1. **Import Original**: Photo imported normally (hash AAA)
2. **Create Version**: You rotate the photo 90° (new hash BBB)
3. **Version Tracking**: System records both AAA and BBB as the same photo
4. **Duplicate Detection**: Re-importing either version → detected as duplicate ✓

**Technical Details:**

- Versions stored in hidden folder: `<archive>/.pyphotoorg_versions/`
- Each version has unique hash but all link to same original
- File hash history tracks all variations automatically
- Works with rotations, crops, color adjustments, format conversions

### Using the VersionManager (Programmatic)

**Note**: GUI integration is planned for v2.5. Currently, version management is available via Python API.

#### Creating Your First Version

```python
from image_modifier import VersionManager, ImageModifier

# Initialize version manager
vm = VersionManager(
    database_path="path/to/PhotoDB.db",
    archive_base="path/to/archive"
)

# Example 1: Rotate an image
archive_file = "/path/to/archive/2024/01/15/photo.jpg"

# Save original as v0 (first time only)
version_id_v0 = vm.save_original_version(archive_file)
print(f"Original saved as: {version_id_v0}")

# Create rotated version
rotated_file = "/tmp/rotated.jpg"
success, output_path, error = ImageModifier.rotate_image(
    archive_file,
    angle=90,
    output_path=rotated_file
)

if success:
    version_id_v1 = vm.create_new_version(
        parent_version_id=version_id_v0,
        modified_file_path=rotated_file,
        modification_type='rotation',
        params={'angle': 90},
        session_id='manual_rotation_001'
    )
    print(f"Rotated version created: {version_id_v1}")
```

#### Viewing Version History

```python
# Get all versions for a photo
original_hash = "abc123...def"  # Hash of original file
history = vm.get_version_history(original_hash)

for version in history:
    print(f"Version {version['version_number']}: {version['modification_type']}")
    print(f"  Created: {version['created_timestamp']}")
    print(f"  Hash: {version['file_hash']}")
    print(f"  Path: {version['storage_path']}")
    print(f"  Active: {version['is_active']}")
```

#### Restoring a Previous Version

```python
# Restore v1 to a specific location
target_path = "/path/to/restored_photo.jpg"
success = vm.restore_version(
    version_id="abc123...def_v1",
    target_path=target_path
)

if success:
    print(f"Version restored to: {target_path}")
```

### Supported Modifications

The `ImageModifier` class provides five modification types:

#### 1. Rotation

```python
from image_modifier import ImageModifier

# Rotate 90° clockwise
success, output, error = ImageModifier.rotate_image(
    input_path="photo.jpg",
    angle=90,  # 90, 180, 270, or custom degrees
    expand=True  # Expand canvas to fit rotated image
)
```

**Features**:
- Arbitrary angles (90°, 180°, 270°, or custom like 45°)
- Preserves EXIF metadata
- Updates orientation tag automatically
- High-quality rotation (no quality loss)

#### 2. Cropping

```python
# Crop to region (left, upper, right, lower)
success, output, error = ImageModifier.crop_image(
    input_path="photo.jpg",
    box=(100, 100, 500, 400)  # pixels from edges
)
```

**Features**:
- Bounding box format: (left, upper, right, lower)
- Validates crop bounds (can't exceed image size)
- Preserves EXIF metadata

#### 3. Resizing

```python
# Resize to specific dimensions
success, output, error = ImageModifier.resize_image(
    input_path="photo.jpg",
    width=1920,
    height=1080,
    maintain_aspect=True  # Keep aspect ratio
)
```

**Features**:
- Optional aspect ratio maintenance
- LANCZOS resampling for best quality
- Preserves EXIF metadata

#### 4. Color Adjustment

```python
# Adjust brightness, contrast, saturation
success, output, error = ImageModifier.adjust_color(
    input_path="photo.jpg",
    brightness=20,   # -100 to +100
    contrast=10,     # -100 to +100
    saturation=-15   # -100 to +100
)
```

**Features**:
- Range: -100 to +100 for each parameter
- 0 = no change, positive = increase, negative = decrease
- All three parameters are optional

#### 5. Format Conversion

```python
# Convert JPEG to PNG
success, output, error = ImageModifier.convert_format(
    input_path="photo.jpg",
    target_format="png",  # jpeg, png, tiff, bmp, gif
    quality=95  # For JPEG/WebP formats
)
```

**Features**:
- Supports: JPEG, PNG, TIFF, BMP, GIF
- Automatic transparency handling
- Preserves EXIF in JPEG and TIFF
- Quality control for lossy formats

### Database Migration

**Automatic Migration**: When you first use `VersionManager`, it automatically migrates your database to schema version 3:

```python
# Migration happens automatically
vm = VersionManager(database_path, archive_base)
# Database is now migrated and ready
```

**What Gets Created**:
- `FileVersions` table - Version history with parent-child relationships
- `ModificationSession` table - Batch operation tracking
- `ModificationLog` table - Per-file operation audit trail
- `FileHashHistory` enhancement - Links versions to duplicate detection

### Syncing Existing Versions

If you created versions before v2.4, sync them to enable duplicate detection:

```python
from database_metadata import DatabaseMetadata

db_meta = DatabaseMetadata("path/to/PhotoDB.db")
synced_count = db_meta.sync_versions_to_hash_history()
print(f"Synced {synced_count} version hashes")
```

**What This Does**:
- Finds all versions in `FileVersions` table
- Adds their hashes to `FileHashHistory`
- Enables duplicate detection for those versions
- Safe to run multiple times (idempotent)

### Version Storage Location

Versions are stored separately from your main archive:

```
<archive>/
├── 2024/
│   ├── 01/
│   │   └── 15/
│   │       └── photo.jpg        ← Original in archive
└── .pyphotoorg_versions/        ← Hidden version storage
    └── by_hash/
        └── ab/                   ← First 2 chars of hash
            ├── abcd1234...ef_v0.jpg    ← Original (v0)
            ├── abcd1234...ef_v1.jpg    ← First modification
            └── abcd1234...ef_v2.jpg    ← Second modification
```

**Storage Notes**:
- Hidden folder (starts with `.`) - won't appear in normal browsing
- Organized by hash prefix for filesystem efficiency
- Version number in filename: `_v0`, `_v1`, `_v2`, etc.
- Original archive file can remain unchanged

### Duplicate Detection with Versions

**Scenario**: You edit a photo externally and re-import it.

**Without Version Management**:
```
1. Import photo.jpg (hash AAA) → stored in archive
2. Edit photo.jpg externally, rotate 90° (hash changes to BBB)
3. Re-import photo.jpg → NOT detected as duplicate ✗
4. Result: Two copies of same photo in archive
```

**With Version Management (v2.4+)**:
```
1. Import photo.jpg (hash AAA) → stored in archive
2. Create version via VersionManager, rotate 90° (hash BBB)
   - System records both AAA and BBB as same photo
3. Re-import rotated photo.jpg → BBB found in hash history ✓
4. Result: Detected as duplicate, import skipped
```

### Best Practices

1. **Save Original First**: Always call `save_original_version()` before creating modifications
   ```python
   v0 = vm.save_original_version(archive_file)  # Do this first
   v1 = vm.create_new_version(v0, modified_file, ...)  # Then create versions
   ```

2. **Use Descriptive Session IDs**: Helps track batches of modifications
   ```python
   session_id = f"vacation_photos_rotation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
   ```

3. **Store Modification Parameters**: Makes operations reproducible
   ```python
   params = {
       'angle': 90,
       'expand': True,
       'reason': 'Photo was sideways from camera'
   }
   ```

4. **Check Return Values**: Always verify operations succeeded
   ```python
   if version_id:
       print(f"Success: {version_id}")
   else:
       print("Failed to create version")
   ```

5. **Sync After Migration**: If you have existing versions, sync them
   ```python
   db_meta.sync_versions_to_hash_history()
   ```

### Troubleshooting Version Management

**Problem**: "Database must be migrated to schema version 3"

**Solution**: Migration should happen automatically, but if it fails:
```bash
cd migrations
python add_modifications_support.py ../PhotoDB.db
```

---

## Prior Revision Archive System

**NEW in v3.0.3** - PyPhotoOrganizer now features a dual-archive system for image rotation that keeps your main archive clean while preserving complete revision history. When you rotate images, the system automatically moves the original version to a separate Prior Revision Archive, ensuring your main archive contains only the latest, current versions.

### Why Use Prior Revision Archive?

**Without Prior Revision Archive:**
- Main archive contains both current and historical versions
- Harder to browse (multiple versions of same photo)
- Manual cleanup required
- Difficult to identify current version

**With Prior Revision Archive:**
- ✅ Main archive contains **only current revisions**
- ✅ Clean, organized browsing experience
- ✅ Automatic historical version management
- ✅ Instant undo capability
- ✅ Complete revision history preserved
- ✅ Transparent duplicate detection across all revisions

### How It Works

**The Basics:**

When you rotate an image in PyPhotoOrganizer:

1. **Original file** moves from Main Archive → Prior Revision Archive
2. **Rotated version** takes the original's place in Main Archive
3. **Database** tracks both file locations
4. **Hash history** records both versions for duplicate detection

**File Organization:**

```
Main Archive (Current Revisions):
/archive/2024/01/15/vacation.jpg        ← Latest version (90° rotated)

Prior Revision Archive (Historical Versions):
/prior_revisions/2024/01/15/vacation_abcd1234.jpg  ← Original (0° rotation)
```

**Note the hash suffix**: Prior revisions use the first 8 characters of the file's hash to prevent filename collisions when multiple revisions exist.

### Setting Up Prior Revision Archive

**Step 1: Configure Location**

1. Open **Archive Settings** tab
2. Scroll to **Prior Revision Archive** section
3. Click **Browse...** and select a directory for prior revisions
4. Click **Save**

**Recommended Locations:**
- Separate drive: `/mnt/backup/prior_revisions/` (best performance)
- Same drive, different folder: `/archive/../prior_revisions/` (easier management)
- Network location: `//NAS/prior_revisions/` (centralized backup)

**Important Rules:**
- ⚠️ Cannot be the same as main archive
- ⚠️ Cannot be inside main archive
- ⚠️ Must be writable
- ⚠️ Must have sufficient disk space

**Step 2: Verify Configuration**

After saving, check the status indicator:
- ✅ **Green checkmark**: Configured and writable
- ❌ **Red X**: Configuration error (check permissions)

### Rotating Images

**Single Image Rotation:**

1. Open **Date Corrections** tab
2. Select a file in the grid
3. Click **Rotate 90° CW**, **Rotate 90° CCW**, or **Rotate 180°**
4. System processes rotation:
   - Creates rotated version
   - Moves original to Prior Revision Archive
   - Places rotated version in Main Archive
   - Updates database records
5. File now appears rotated in preview

**Batch Rotation:**

1. Select multiple files (Shift+Click or Ctrl+Click)
2. Choose rotation angle (same angle applied to all)
3. Click **Rotate Selected**
4. Progress dialog shows per-file status
5. All originals moved to Prior Revision Archive

**Rotation Angles:**
- **90° CW**: Rotate clockwise (portrait → landscape)
- **90° CCW**: Rotate counter-clockwise (landscape → portrait)
- **180°**: Flip upside down
- **Custom**: Enter any angle (0-359°)

### Understanding Revision History

**Example Timeline:**

```
Day 1: Import vacation.jpg
  Main Archive:    vacation.jpg (hash AAA, original)
  Prior Archive:   (empty)

Day 2: Rotate 90° clockwise
  Main Archive:    vacation.jpg (hash BBB, 90° rotation)
  Prior Archive:   vacation_aaaabbbb.jpg (hash AAA, original)

Day 3: Rotate 180° (total 270°)
  Main Archive:    vacation.jpg (hash CCC, 270° rotation)
  Prior Archive:   vacation_aaaabbbb.jpg (hash AAA, original)
                   vacation_bbbbcccc.jpg (hash BBB, 90° rotation)
```

**Key Concepts:**

- **Current Revision**: Always in Main Archive with original filename
- **Historical Revisions**: In Prior Archive with hash-suffixed filenames
- **Revision Chain**: Each revision knows its parent via database linkage
- **Hash Tracking**: All revision hashes tracked for duplicate detection

### Undoing Rotations

**Single Undo:**

1. Select rotated file in Photo Review app
2. Click **Undo Last Rotation**
3. System performs undo:
   - Moves current revision → Prior Archive
   - Moves parent revision → Main Archive
   - Swaps filenames
   - Updates database records
4. Previous revision restored

**Multiple Undos:**

You can undo multiple times, stepping backward through revision history:

```
Current: CCC (270°) → Undo → BBB (90°) → Undo → AAA (original)
```

**Undo Limitations:**
- Can only undo if parent revision exists
- Cannot undo past the original (v0)
- Undo operation is itself reversible (undo the undo)

### Duplicate Detection with Revisions

**Scenario**: You rotate a photo, then try to re-import the original from your phone.

**What Happens:**

1. **Import Process**: System calculates hash of phone file → AAA
2. **Hash Check**: System checks FileHashHistory table
3. **Match Found**: AAA matches original version (now in Prior Archive)
4. **Result**: ✅ Duplicate detected, import skipped

**This Works For:**
- Re-importing original after rotation
- Re-importing any historical revision
- Re-importing current revision from different source
- Any variation that was previously processed

**Why It Works:**
- All revision hashes stored in FileHashHistory
- Duplicate detection checks both current and historical hashes
- Works transparently across archives

### Managing Prior Revision Archive

**Checking Disk Usage:**

```bash
# Linux/macOS
du -sh /path/to/prior_revisions

# Windows (PowerShell)
Get-ChildItem "C:\PriorRevisions" -Recurse | Measure-Object -Property Length -Sum
```

**Manual Cleanup:**

Prior revisions accumulate over time. If disk space is limited:

1. **Identify Old Revisions**: Check timestamps in Prior Archive
2. **Delete Unwanted Files**: Manually delete revision files
3. **Update Database** (optional): Remove records from UniquePhotos for deleted files

**⚠️ Warning**: Deleting prior revisions permanently removes undo capability for those files.

**Automatic Cleanup** (Future Enhancement):
- Retention policies (keep last N revisions)
- Age-based cleanup (delete revisions older than X days)
- Size-based limits (delete oldest when exceeding X GB)

### Best Practices

**1. Configure Before Rotating:**
Always set up Prior Revision Archive before performing rotations:
```
✓ Setup first: Configure → Verify → Rotate
✗ Don't: Rotate → "Error: Prior archive not configured"
```

**2. Choose Appropriate Location:**
- **Performance**: Use SSD or fast drive for main archive, HDD acceptable for prior archive
- **Backup**: Place prior archive on separate physical drive for redundancy
- **Capacity**: Ensure sufficient space (expect ~2x space per rotation)

**3. Monitor Disk Space:**
Check periodically:
- Main archive: Should stay relatively constant (only current revisions)
- Prior archive: Grows with each rotation
- Plan for cleanup when approaching capacity limits

**4. Test Undo Before Deleting:**
Before manually cleaning up prior revisions:
- Test undo on a few files to verify functionality
- Confirm you don't need those historical versions
- Consider backing up prior archive before deletion

**5. Document Rotation Rationale:**
Use Photo Review app to track:
- Why file was rotated (camera was sideways)
- Original orientation
- Date rotation was performed

### Troubleshooting

**Problem**: "Prior Revision Archive not configured"

**Solution**:
1. Open Archive Settings tab
2. Set Prior Revision Archive location
3. Verify green checkmark appears
4. Retry rotation

**Problem**: "Failed to move original to prior archive"

**Possible Causes**:
- Insufficient disk space in prior archive
- Prior archive directory deleted or unavailable
- Permission issues (not writable)
- File locked by another application

**Solution**:
1. Check disk space: `df -h /path/to/prior`
2. Verify directory exists and is writable
3. Check file permissions
4. Close any applications that might have file open

**Problem**: "Undo failed - parent revision not found"

**Possible Causes**:
- Parent file manually deleted from prior archive
- Prior archive moved to different location
- Database records corrupted

**Solution**:
1. Check if parent file exists at recorded path
2. Verify prior archive location unchanged
3. Check database integrity

**Problem**: "File collision during undo"

**Cause**: Target filename already exists in main archive

**Solution**:
1. System should automatically generate unique name (_1, _2, etc.)
2. If error persists, manually rename conflicting file
3. Retry undo operation

### Migration for Existing Installations

**Automatic Migration:**

When you open an existing database with v3.0.3+:
1. System automatically adds `prior_revision_archive_location` column
2. No data loss or corruption
3. Feature disabled until you configure location
4. Existing rotations (if any) remain in old format

**No Need to Convert:**
- Old rotations work as-is
- New rotations use Prior Revision Archive (after configuration)
- Mixed mode supported indefinitely

**Clean Slate Option:**

If you want to start fresh with Prior Revision Archive:
1. Backup your current database
2. Configure Prior Revision Archive location
3. Future rotations use new system automatically
4. Old files remain in place (no automatic migration)

### Performance Considerations

**Rotation Performance:**

| Resolution | Typical Rotation Time |
|------------|----------------------|
| 1-2 MP     | 100-200ms           |
| 8-12 MP    | 200-350ms           |
| 24+ MP     | 350-500ms           |

**Bottleneck**: Image processing (decode, rotate, encode), not file operations.

**Undo Performance:**

| Operation     | Typical Time |
|---------------|--------------|
| File swap     | 50-150ms     |
| Database update | <10ms       |

**Bottleneck**: Disk I/O (faster on SSD).

**Disk Space Impact:**

Each rotation approximately doubles storage:
- Original: 2.5 MB → Prior Archive
- Rotated: 2.6 MB → Main Archive
- Total: 5.1 MB (was 2.5 MB)

**Multiple rotations accumulate**:
- 3 rotations = 4 versions = 4× storage
- Plan accordingly for disk capacity

### Advanced: Database Schema

For developers and power users:

**DatabaseMetadata Table:**
```sql
-- New column added in v3.0.3
ALTER TABLE DatabaseMetadata
ADD COLUMN prior_revision_archive_location TEXT;
```

**UniquePhotos Table:**
```sql
CREATE TABLE UniquePhotos (
    file_hash TEXT PRIMARY KEY,       -- Current file hash
    file_name TEXT NOT NULL,          -- Current path (main OR prior archive)
    revised_photo TEXT,               -- Parent revision hash (NULL = original)
    original_hash TEXT,               -- Links all revisions to same original
    ...
);
```

**FileHashHistory Table:**
```sql
CREATE TABLE FileHashHistory (
    current_file_hash TEXT,           -- Original file hash
    historical_hash TEXT,             -- Any revision hash
    reason TEXT,                      -- 'rotation_revision', 'original', etc.
    ...
);
```

**Querying Revisions:**
```sql
-- Find all revisions of a photo
SELECT * FROM UniquePhotos
WHERE original_hash = 'abc123...def'
ORDER BY file_hash;

-- Find current revision (in main archive)
SELECT * FROM UniquePhotos
WHERE original_hash = 'abc123...def'
  AND file_name LIKE '%archive%'
  AND file_name NOT LIKE '%prior%';

-- Find prior revisions (in prior archive)
SELECT * FROM UniquePhotos
WHERE original_hash = 'abc123...def'
  AND file_name LIKE '%prior%';
```

---

## Archive Change Detection

**NEW** - PyPhotoOrganizer can now detect when archive files have been modified externally (e.g., edited in Photoshop, Lightroom, or other photo software). When external modifications are detected, the system preserves original versions and creates revision records.

### Why Use Archive Change Detection?

If you edit photos in external software:
- The file's content changes, but PyPhotoOrganizer doesn't know about it
- The original version might be lost
- Duplicate detection could be affected

With Archive Change Detection:
- ✅ External modifications are **automatically detected**
- ✅ Original versions are **preserved** in Prior Revision Archive
- ✅ Revision records are **created** for tracking
- ✅ All versions are **tracked** for duplicate detection

### How It Works

The scanner compares the current pixel content of each archive file against the stored content hash:

1. **Unchanged files**: Content hash matches → no action needed
2. **Modified files**: Content hash differs → external modification detected
   - Original version located (from backup or source)
   - Original copied to Prior Revision Archive
   - Revision record created in database
   - Operation logged to audit trail

### Running a Change Scan

1. Open the **Archive Maintenance** tab
2. Find the **"Archive Change Detection"** section
3. Choose scan scope:
   - **Scan entire archive**: Check all files
   - **Scan specific folder**: Check only files in a selected folder
4. Click **"Scan for External Changes"**
5. Review results when complete

### Prerequisites

Before scanning, ensure:

- **Content hashes calculated**: Files need content hashes to detect changes. Run "Calculate Content Hashes" in System Settings if needed.
- **Prior Revision Archive configured**: Required to store original versions. Configure in Archive Settings tab.
- **Backup location (optional)**: If configured, originals are first sought here.

### Understanding Results

| Metric | Meaning |
|--------|---------|
| Files scanned | Total files checked |
| Unchanged | Files with matching content hashes |
| Modifications detected | Files that differ from stored content |
| Revisions created | Successful revision records made |
| Originals from backup | Originals found in backup location |
| Originals from source | Originals found at original source path |
| Originals not found | Revisions created without preserving original |
| Errors | Files that encountered processing errors |
| Skipped (videos) | Videos don't have content hashes |
| Skipped (no content hash) | Files needing content hash backfill |

### Viewing External Modifications

After a scan, view detected modifications in **Import History**:

1. Go to the **Import History** tab
2. Use the **Show** dropdown
3. Select **"External Modifications"**
4. View all files flagged as externally modified

### Best Practices

1. **Run content hash backfill first**: Ensure all files have content hashes before scanning
2. **Configure backup location**: Increases chance of preserving originals
3. **Scan periodically**: Run after known external editing sessions
4. **Review results**: Check what was modified and why

### Example Workflow

1. Import photos into archive
2. Edit some photos in Lightroom (externally)
3. Run "Scan for External Changes"
4. System detects modified files
5. Originals preserved in Prior Revision Archive
6. Continue working with confidence that history is tracked

---

## Bulk Delete Matching Files

PyPhotoOrganizer can bulk delete archive files that match files in a reference folder. This is useful when you want to remove photos that:
- Are already backed up elsewhere (cloud storage, external drive)
- Are synced to another device and no longer needed in the main archive
- Match a "delete manifest" folder you've prepared

### Prerequisites

Before using Bulk Delete, ensure:
1. **Delete Vault is configured**: Go to System Settings → Delete Vault Location
2. **Database is loaded**: Select your database in the main window

### How It Works

The bulk delete operation has two phases:

**Phase 1 - Scan:**
1. Scans all files in the reference folder
2. Calculates SHA-256 hash of each file
3. Checks if hash exists in your archive database
4. Reports matches and non-matches

**Phase 2 - Delete:**
1. Shows preview dialog with matched files
2. Requires explicit confirmation before proceeding
3. Moves matched archive files to Delete Vault (soft-delete)
4. Removes from albums (if configured)
5. Logs all operations to audit trail

### Step-by-Step Instructions

1. Open the **Import GUI** (`python main_gui.py`)

2. Go to the **Archive Maintenance** tab

3. Find the **"Bulk Delete Matching Files"** section

4. Click **"Browse..."** to select your reference folder
   - This folder contains files you want to match against the archive
   - All files in this folder (and subfolders) will be scanned

5. Click **"Scan for Matches"**
   - Progress bar shows scanning progress
   - Wait for scan to complete

6. Review the **Preview Dialog** that appears:
   - **"To Delete" tab**: Files that match (will be deleted from archive)
   - **"Not in Archive" tab**: Files that weren't found in archive
   - Check the summary stats (matches, not found, total size)

7. If satisfied, click **"Delete Matched Files"**
   - A confirmation dialog appears
   - Click "Yes" to proceed with deletion

8. Wait for deletion to complete
   - Files are moved to Delete Vault
   - Progress is shown in the UI

9. Review results in **Import History** tab
   - Use "Show: Bulk Delete Operations" filter to see all operations

### Viewing Bulk Delete History

1. Go to **Import History** tab
2. Use the **Show** dropdown
3. Select **"Bulk Delete Operations"**
4. View all files processed by bulk delete:
   - **bulk_delete_matched** with status **success**: File deleted successfully
   - **bulk_delete_matched** with status **failed**: Deletion failed (see Details)
   - **bulk_delete_not_found** with status **skipped**: File not in archive

### Use Cases

**1. Cleaning up after cloud sync:**
```
You've synced photos to Google Photos. Now you want to remove those
exact files from your local archive to save space.

Steps:
1. Download/export the synced photos to a reference folder
2. Use Bulk Delete to match and remove from archive
3. Delete the reference folder after verifying
```

**2. Removing duplicates from another backup:**
```
You have photos on an external drive that are also in your archive.
You want to keep only the archive copies.

Steps:
1. Point Bulk Delete to the external drive folder
2. Scan to see what matches
3. Delete matches from archive (or keep archive, delete external)
```

**3. Using a "delete manifest":**
```
You've prepared a folder of photos you want to remove from the archive.

Steps:
1. Copy/move the unwanted photos to a "to_delete" folder
2. Use Bulk Delete with that folder as reference
3. All matching archive files are removed
```

---

## Delete Vault and File Recovery

The **Delete Vault** provides a safety net for all deleted files. When you delete photos from the archive (whether individually, via bulk delete, or through Photo Review), files are moved to the Delete Vault rather than permanently deleted.

### Why a Delete Vault?

- **Accidental deletion protection**: Recover files deleted by mistake
- **Audit trail**: Track what was deleted and when
- **Delayed permanent deletion**: Review before final purge
- **Preserves folder structure**: Easy to find and restore specific files

### Configuring the Delete Vault

1. Go to **System Settings** tab
2. Find **"Delete Vault Location"**
3. Click **"Browse..."** to select a folder
4. Recommended: Use a separate drive or clearly labeled folder

**Important**: The Delete Vault should have sufficient space to hold deleted files until you're ready to purge them.

### Viewing Deleted Files

1. Go to **Archive Maintenance** tab
2. Find **"Delete Vault Management"** section
3. Click **"View Vault Contents"**

The Deleted Files dialog shows:
- Original archive path
- Vault path (where file is now)
- Deletion timestamp
- Deletion reason
- File hash

### Restoring Deleted Files

**To restore accidentally deleted files:**

1. Open **Archive Maintenance** tab
2. Click **"View Vault Contents"**
3. Find the file(s) you want to restore
4. Select the file(s) in the list
5. Click **"Restore Selected"**

The restore operation:
- Copies file back to original archive location
- Recreates folder structure if needed
- Updates database to mark file as restored
- Removes file from Delete Vault

### Recovering from a Bad Bulk Delete

If you accidentally deleted the wrong files with Bulk Delete:

**Immediate Recovery (files still in vault):**

1. Go to **Archive Maintenance** tab
2. Click **"View Vault Contents"**
3. Sort by **"Deleted Date"** (newest first)
4. Select all files from the incorrect deletion session
5. Click **"Restore Selected"**
6. Verify files are back in archive

**Identifying the Wrong Files:**

If you're not sure which files were incorrect:

1. Go to **Import History** tab
2. Find the bulk delete session (look for recent sessions with `operation_mode='bulk_delete'`)
3. Click on the session to view file details
4. Use "Show: Bulk Delete Operations" filter
5. Review the **source_path** column to see which reference files matched
6. Cross-reference with vault contents to select correct files for restore

**Partial Recovery:**

If only some files were incorrectly deleted:

1. Open Delete Vault contents
2. Use search/filter to find specific files
3. Restore only those files
4. Leave correctly deleted files in vault

### Permanently Purging the Delete Vault

**Warning**: This action is irreversible!

To permanently delete all files in the vault:

1. Go to **Archive Maintenance** tab
2. Find **"Delete Vault Management"** section
3. Click **"Permanently Purge Vault"** (red button)
4. Read the warning carefully
5. Click "Yes" to confirm
6. Click "Yes" again to double-confirm
7. Files are permanently deleted

**Best Practice**: Only purge after:
- Verifying no files need to be restored
- Checking recent bulk delete operations were correct
- Allowing a "cooling off" period (days or weeks)

### Delete Vault Storage Structure

Files in the Delete Vault maintain their relative paths:

```
Delete Vault/
├── 2024/
│   ├── 01/
│   │   └── 15/
│   │       └── IMG_1234.jpg
│   └── 03/
│       └── 20/
│           └── photo.png
└── prior_revisions/
    └── 2024/
        └── IMG_1234_abc123.jpg
```

This structure makes it easy to:
- Browse deleted files by date
- Find specific files quickly
- Understand what was in the archive

---

**Problem**: Versions created but duplicates not detected

**Solution**: Run sync to add version hashes to history:
```python
from database_metadata import DatabaseMetadata
db_meta = DatabaseMetadata("PhotoDB.db")
db_meta.sync_versions_to_hash_history()
```

---

**Problem**: Version storage consuming too much space

**Solution**: Old/inactive versions can be deleted manually:
1. Find versions: `<archive>/.pyphotoorg_versions/by_hash/`
2. Check `is_active` flag in database
3. Delete inactive versions if no longer needed
4. Database records remain for duplicate detection

---

**Problem**: Want to apply version to replace original

**Solution**: (Manual process until GUI is added)
1. Restore version to temp location
2. Copy to archive location (overwrite original)
3. Update `UniquePhotos` table with new hash
4. This is complex - wait for v2.5 GUI support

### Future Enhancements (v2.5 Planned)

- **Image Editor Tab**: GUI for all modification operations
- **Version History Viewer**: Visual timeline of all versions
- **One-Click Restore**: Restore any version with single click
- **Apply Version**: Replace original with selected version
- **Batch Operations**: Modify multiple photos at once
- **Comparison View**: Side-by-side before/after preview
- **Undo Support**: Revert modification sessions

---

## Photo Review App

The **Photo Review** app (`photo_review.py`) is a standalone companion tool for browsing and managing photos in your archive. It provides a modern grid-based interface optimized for reviewing large photo collections.

### Launching Photo Review

```bash
python photo_review.py
```

Or from the main application, use File > Open Photo Review.

### Interface Overview

The Photo Review window has four main areas:

1. **Search Bar** (top): Quick search with Ctrl+K shortcut
2. **Query Panel** (left): Filter and search options
3. **Photo Grid** (center): Thumbnail view of photos
4. **Preview Panel** (right): Selected photo preview

### Query Panel Features

The query panel has collapsible sections:

- **Browse Folders**: Navigate archive folder structure
- **Search Photos**: Text search across filenames and paths
- **Filter Status**: Filter by date status (Unreliable, Corrected, Reorganized)
- **Saved Queries**: Save and recall filter combinations

**Saved Queries**: Click a saved query to automatically apply its filters and execute the search.

### Photo Grid

- **Thumbnail Size**: Use slider to adjust thumbnail size
- **Selection**: Click to select, Ctrl+Click for multi-select, Shift+Click for range
- **Status Badges**: Colored pills show photo status:
  - **Amber "Unreliable"**: Date needs verification
  - **Green "Needs Move"**: Corrected, pending reorganization
  - **Blue "Done"**: Fully processed
  - **Violet "Revisions"**: Has version history
- **Checkmarks**: Blue circle with checkmark shows selected photos

### Selection Action Bar

When photos are selected, a floating action bar appears with quick actions:
- **Delete**: Move selected photos to delete vault
- **Rotate**: Rotate selected photos
- **Correct Date**: Open date correction dialog
- **Deselect**: Clear selection

### Preview Panel

Shows the selected photo with:
- Rubber band zoom (drag to select area, double-click to reset)
- File details (name, date, status)
- Double-click a photo to open full preview window

### Detachable Preview Window

Double-click a photo or use the context menu to open the full preview window:

- **Large Image View**: Zoomable preview with rubber band selection
- **File Details Panel**: Source path, archive path, dates, status, hash
- **Revisions Panel**: View all versions of the photo
- **Source Actions**: Open source file, open source folder, copy path
- **Archive Actions**: Open archive file, open archive folder, copy path
- **Correct Date**: Open date correction dialog
- **Close Button** (red): Prominently positioned for easy closing

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+K | Focus search bar |
| Delete | Delete selected photos |
| Ctrl+A | Select all |
| Escape | Deselect all |

### Theme Support

Photo Review supports both dark and light modes. The theme automatically matches your system preference, or you can toggle it manually.

### Close Button

Both the main window and preview window have a **red Close button** in the bottom-right corner for easy, visible window closing.

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

The file grid shows all operations with filtering options:
- **Show dropdown**: Filter by All Files, New Files, Duplicates, Content Duplicates, Filtered, Recently Overridden, External Modifications, Bulk Delete Operations, or Errors
- **Search box**: Text search across all columns
- Columns: Source Folder, Filename, Destination, Operation, Status, Hash, Details

### Previewing Files

**Detached Preview Window** (Recommended):
- **Double-click** any file row to open the large preview window
- Shows comprehensive file details:
  - Database Info (hash, paths, dates, status)
  - File Information (size, type, modified date)
  - Image Properties (dimensions, megapixels, aspect ratio, format)
  - EXIF Data (camera, exposure, GPS, etc.)
  - Revisions (if file has been rotated/modified)
- Preview **automatically updates** when you select a different file
- Can be moved to a second monitor for dual-screen workflows

**Inline Preview Panel** (Optional):
- Click "Show Preview Panel" button to reveal inline preview
- Shows image preview and file details in the bottom section
- Hidden by default to maximize grid space
- Performance optimized: only loads when visible

### File Actions

When a file is selected:
- **Open Source File**: Open the original file with default application
- **Open Source Folder**: Open folder containing the source file
- **Copy Source Path**: Copy file path to clipboard
- **Process File(s)**: Reprocess selected files with current settings
- **Override Skip**: Import filtered files bypassing size/dimension filters
- **Undo Override**: Undo the last override skip operation
- **Select All Visible**: Select all visible rows in the current view

### Override Skip Feature

The **Override Skip** button allows you to import files that were previously filtered out (skipped due to file size, dimensions, or other filter criteria). This is useful when:

- A legitimate photo was incorrectly filtered as an icon/thumbnail
- You want to import small images that were excluded by size filters
- You need to import files that don't meet the default dimension requirements

**How to use Override Skip:**

1. Go to the **Import History** tab
2. Use the **Show** dropdown and select **"Filtered (Icons/Thumbnails)"**
3. Select one or more filtered files (or use **Select All Visible** button)
4. Click the **Override Skip** button
5. Review the confirmation dialog showing:
   - Number of files to import
   - Total file size
   - Destination archive location
   - Organization template
6. Click **Yes** to proceed

**What happens during processing:**

- Selected rows are highlighted yellow to show they're being processed
- As each file completes, its row is immediately removed from the view
- You can see real-time progress in the progress dialog
- The current session and scroll position are preserved

**After completion:**

- Files are imported directly to your archive, bypassing all PhotoFilter criteria
- Duplicate detection still applies (files already in archive are skipped)
- If the source folder has an album association, files are also added to that album
- Successfully imported files appear in the **"Recently Overridden"** filter
- A completion message shows the results (successful, duplicates skipped, failed)

**Viewing imported files:**

After Override Skip completes, you can view the imported files by:
1. Using the **Show** dropdown and selecting **"Recently Overridden"**
2. Or switching to **"New Files (Added to Archive)"** to see all imported files

**Undo Override Skip:**

If you made a mistake, you can undo the last override skip operation:

1. Click the **Undo Override** button
2. Review the confirmation dialog
3. Click **Yes** to proceed

This will:
- Delete the imported files from your archive
- Remove entries from the database
- Restore the rows to the Filtered view
- Your source files are never affected

**Important notes:**

- Only files with "skip_filtered" status can be processed with Override Skip
- Source files must still exist on disk
- If some selected files no longer exist, you'll see a warning but valid files will still be imported
- Undo only works for the most recent override skip operation

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

## Cloud Storage

PyPhotoOrganizer supports storing your photo archive in cloud storage services like Amazon S3. This allows you to:

- **Off-site backup**: Keep a copy of your archive in the cloud for disaster recovery
- **Cost-effective archival**: Use cloud storage tiers like S3 Intelligent-Tiering or Glacier for long-term storage
- **Multi-location access**: Access your archive from anywhere with cloud storage

> **Note**: Cloud storage is currently in beta. Local storage remains the recommended option for most users.

### Supported Cloud Providers

| Provider | Status | Notes |
|----------|--------|-------|
| **Amazon S3** | Supported | Full support including storage classes |
| **Azure Blob Storage** | Planned | Coming in future release |
| **Google Cloud Storage** | Planned | Coming in future release |
| **Backblaze B2** | Planned | S3-compatible API |

### Prerequisites for S3

Before using Amazon S3 storage, you need:

1. **AWS Account**: Sign up at [aws.amazon.com](https://aws.amazon.com)
2. **S3 Bucket**: Create a bucket in your preferred region
3. **AWS Credentials**: Configure one of:
   - AWS CLI credentials (`~/.aws/credentials`)
   - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
   - IAM role (if running on AWS infrastructure)
4. **Python Package**: Install boto3 (`pip install boto3`)

#### Setting Up AWS Credentials

**Option 1: AWS CLI (Recommended)**
```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region, Output format
```

**Option 2: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Option 3: Credentials File**

Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key

[photo-archive]
aws_access_key_id = another_key
aws_secret_access_key = another_secret
```

#### Required S3 Permissions

Your AWS user/role needs these permissions on the target bucket:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

### Configuring Cloud Storage

Cloud storage is configured per-vault in the **Archive Settings** tab.

#### Available Vaults

| Vault | Description | Cloud Recommended |
|-------|-------------|-------------------|
| **Main Archive** | Your organized photo collection | Yes |
| **Video Archive** | Separate storage for videos | Yes |
| **Prior Revision Archive** | Original versions before edits | Optional |
| **Delete Vault** | Soft-deleted files | No (keep local) |

#### Configuration Steps

1. Open the **Archive Settings** tab
2. Scroll to **Cloud Storage (Beta)** section
3. For each vault you want to configure:
   - Select **Provider**: Local, Amazon S3, etc.
   - Enter provider-specific settings (see below)
4. Click **Test Connection** to verify settings
5. Settings are saved automatically

#### S3 Configuration Options

| Setting | Description | Example |
|---------|-------------|---------|
| **Bucket** | S3 bucket name | `my-photo-archive` |
| **Prefix** | Folder path within bucket | `photos/archive` |
| **Region** | AWS region | `us-east-1`, `eu-west-1` |
| **Storage Class** | S3 storage tier | See table below |
| **AWS Profile** | Named profile from credentials | `default`, `photo-archive` |

#### S3 Storage Classes

| Class | Use Case | Cost | Access Time |
|-------|----------|------|-------------|
| **STANDARD** | Frequently accessed | Higher | Immediate |
| **INTELLIGENT_TIERING** | Unknown access patterns | Auto-optimized | Immediate |
| **STANDARD_IA** | Infrequent access (monthly) | Lower | Immediate |
| **ONEZONE_IA** | Non-critical, infrequent | Lowest IA | Immediate |
| **GLACIER_IR** | Archive, rare access | Lower | Minutes |
| **GLACIER** | Long-term archive | Very low | Hours |
| **DEEP_ARCHIVE** | Compliance/backup | Lowest | 12+ hours |

**Recommendation**: Use `INTELLIGENT_TIERING` for most photo archives. It automatically moves objects between tiers based on access patterns.

### Syncing to Cloud

Once configured, you can sync your local archive to cloud storage.

#### Manual Sync

1. Go to **Archive Settings** tab
2. In the **Cloud Sync** section, click **Sync Now**
3. Progress bar shows upload status
4. Click **Stop** to pause at any time

#### Sync Status

Click **Check Status** to see sync statistics:

```
Main Archive:
  Total files: 15,234
  Synced: 12,100 (79.4%)
  Pending: 500
  Failed: 12
  Needs sync: 2,622
```

#### What Gets Synced

- New photos imported to the archive
- Photos not yet uploaded to cloud
- Sync is additive - cloud files are never deleted automatically

#### Failed Uploads

If uploads fail (network issues, permissions):

1. Click **Check Status** to see failed count
2. Fix the underlying issue (network, credentials)
3. Click **Sync Now** to retry failed uploads

### Downloading from Cloud

You can download files from cloud storage to local:

- **On-demand**: Files are downloaded when accessed in Photo Review
- **Batch download**: Coming in future release

### Conflict Resolution

When files differ between local and cloud:

| Conflict Type | Description | Resolution Options |
|---------------|-------------|-------------------|
| **Size Mismatch** | Same file, different sizes | Keep Local / Keep Cloud / Keep Both |
| **Missing Local** | File in cloud but not local | Download / Skip |
| **Missing Cloud** | File local but not in cloud | Upload / Skip |

### Best Practices

#### For Archive Storage

1. **Use Intelligent-Tiering** for the main archive
2. **Keep Delete Vault local** - you need quick access to recover files
3. **Test connection** before large syncs
4. **Monitor costs** in AWS Console

#### For Backup Strategy

1. **Local + Cloud**: Keep local copy as primary, cloud as backup
2. **Sync regularly**: Run sync after each import session
3. **Verify uploads**: System automatically verifies file hashes

#### For Cost Management

1. **Choose appropriate storage class** based on access patterns
2. **Use lifecycle policies** in S3 to transition old files to Glacier
3. **Set bucket policies** to prevent accidental public access
4. **Enable versioning** in S3 for additional protection

### Troubleshooting Cloud Storage

#### "Connection failed" Error

1. Verify AWS credentials are configured correctly
2. Check bucket name and region are correct
3. Ensure your network allows HTTPS to AWS
4. Verify IAM permissions include required S3 actions

#### "Access Denied" Error

1. Check bucket policy allows your IAM user
2. Verify bucket name is spelled correctly
3. Check if bucket is in expected region
4. Ensure credentials are for correct AWS account

#### Slow Upload Speeds

1. Files are uploaded sequentially for reliability
2. Large files (>8MB) use multipart upload automatically
3. Check network bandwidth to AWS region
4. Consider using a closer AWS region

#### Sync Stuck or Not Progressing

1. Click **Stop** to halt current sync
2. Check **Check Status** for error counts
3. Review application logs for detailed errors
4. Retry with **Sync Now**

### Cloud Storage Limitations (Beta)

Current limitations that will be addressed in future releases:

1. **S3 only**: Azure and GCS support coming soon
2. **Upload only**: Batch download interface pending
3. **No automatic sync**: Must manually trigger sync
4. **No bandwidth throttling**: Uses full available bandwidth
5. **No encryption options**: Uses server-side encryption only

---

## Auto-Import Service

The Auto-Import Service is a background service that automatically monitors directories for new photos and videos, imports them to your archive, and sends email reports. It's ideal for automated workflows like:

- Automatically importing photos from phone sync folders
- Processing photos dropped into a "to import" folder
- Scheduled imports from network drives or cloud sync locations

### Quick Start

1. **Generate a configuration file**:
   ```bash
   python -m auto_import generate-config -o autoimport.yaml
   ```

2. **Edit the configuration** to set your database path and watch directories

3. **Validate the configuration**:
   ```bash
   python -m auto_import validate -c autoimport.yaml
   ```

4. **Run a single import cycle** (test mode):
   ```bash
   python -m auto_import run-once -c autoimport.yaml
   ```

5. **Start the service**:
   ```bash
   python -m auto_import start -c autoimport.yaml
   ```

### Configuration File

The service uses a YAML configuration file with these main sections:

```yaml
# Service settings
service:
  database_path: ~/Photos/PhotoDB.db  # Required: your PyPhotoOrganizer database
  pid_file: /var/run/pyphoto-autoimport.pid  # For daemon mode
  log_file: /var/log/pyphoto-autoimport.log  # Empty for stdout
  log_level: INFO  # DEBUG, INFO, WARNING, ERROR

# Schedule settings
schedule:
  mode: interval  # interval, cron, or continuous
  interval_minutes: 60  # For interval mode
  cron_expression: "0 2 * * *"  # For cron mode (2 AM daily)
  quiet_hours:
    start: "23:00"  # Skip imports during these hours
    end: "06:00"
  run_on_startup: true  # Run immediately when service starts

# Directories to watch
watch_directories:
  - path: ~/PhoneBackup/DCIM
    enabled: true
    recursive: true  # Include subdirectories
    min_file_age_seconds: 120  # Wait for sync to complete
    album_id: 1  # Optional: auto-add to album
    name: "Phone Photos"  # Friendly name for reports

  - path: ~/Downloads/Photos
    enabled: true
    recursive: false
    min_file_age_seconds: 60

# Processing options
processing:
  copy_mode: true  # true=copy, false=move source files
  max_files_per_run: 0  # 0=unlimited
  max_bytes_per_run: 0  # 0=unlimited

# Email notifications
notifications:
  enabled: true
  email:
    enabled: true
    recipients:
      - admin@example.com
    smtp:
      server: smtp.gmail.com
      port: 587
      username: your-email@gmail.com
      password_env: SMTP_PASSWORD  # Read from environment variable
      use_tls: true
  reports:
    on_success: true
    on_failure: true
    on_no_changes: false  # Don't spam when nothing happens
    include_file_list: true
    max_files_in_report: 50
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `generate-config` | Generate a default configuration file |
| `validate` | Validate configuration and check watch directories |
| `start` | Start the service (blocks until stopped) |
| `run-once` | Run a single import cycle and exit |
| `status` | Show service status and watch directory info |
| `stop` | Stop a running service |
| `test-email` | Send a test email to verify configuration |
| `clear-state` | Clear processed file tracking (re-import files) |

### Schedule Modes

**Interval Mode** (default):
- Runs every N minutes
- Good for regular automated imports
- Example: `interval_minutes: 60` runs every hour

**Cron Mode**:
- Runs at specific times using cron syntax
- Good for scheduled maintenance windows
- Example: `cron_expression: "0 2 * * *"` runs at 2 AM daily

**Continuous Mode**:
- Runs as fast as possible
- Good for initial bulk imports
- Use with caution on systems with limited resources

### Quiet Hours

Configure times when imports should be skipped:

```yaml
schedule:
  quiet_hours:
    start: "23:00"
    end: "06:00"
```

This prevents imports during nighttime when:
- Network drives might be unmounted
- System backups might be running
- You want to avoid disk activity

### Album Integration

Automatically add imported photos to albums by specifying `album_id`:

```yaml
watch_directories:
  - path: ~/PhoneBackup/iPhone
    album_id: 3  # Add all photos to album ID 3
```

Get album IDs from the Photo Review app's Albums panel.

### Email Reports

The service sends HTML email reports after each import cycle:

**Successful Import Report**:
- Number of files scanned, imported, duplicates, filtered, failed
- List of imported files (configurable limit)
- Processing duration and data size

**Failure Report**:
- Error messages
- Files that failed to process
- Suggested remediation steps

**Test Email**:
```bash
python -m auto_import test-email -c autoimport.yaml
```

### Running as a System Service

**Linux (systemd)**:

Create `/etc/systemd/system/pyphoto-autoimport.service`:
```ini
[Unit]
Description=PyPhotoOrganizer Auto-Import Service
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/PyPhotoOrganizer
ExecStart=/usr/bin/python3 -m auto_import start -c /path/to/autoimport.yaml
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pyphoto-autoimport
sudo systemctl start pyphoto-autoimport
```

**macOS (launchd)**:

Create `~/Library/LaunchAgents/com.pyphotoorganizer.autoimport.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pyphotoorganizer.autoimport</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-m</string>
        <string>auto_import</string>
        <string>start</string>
        <string>-c</string>
        <string>/path/to/autoimport.yaml</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/PyPhotoOrganizer</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Then:
```bash
launchctl load ~/Library/LaunchAgents/com.pyphotoorganizer.autoimport.plist
```

### Troubleshooting Auto-Import

**Service won't start**:
- Check configuration with `validate` command
- Verify database path exists and is accessible
- Check log file for detailed errors

**Files not being imported**:
- Check `min_file_age_seconds` - files must be older than this
- Verify watch directory is `enabled: true`
- Check if files match the file patterns (images/videos only)
- Use `status` command to check directory availability

**Duplicate emails or imports**:
- Check if multiple service instances are running
- Use `clear-state` to reset tracking database

**Permission errors**:
- Ensure service user has read access to watch directories
- Ensure service user has write access to archive directory
- Check database file permissions

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

#### "Database Error" dialog on startup
- The database file may be corrupted
- Check the `db_snapshots/` folder for automatic backups
- See [Restoring a Corrupt Database](#restoring-a-corrupt-database) for recovery steps

#### "Pending Operations Found" dialog on startup
- A previous import was interrupted (crash, power loss, force quit)
- Click **Yes** to recover: verified files are kept, incomplete files are cleaned up
- Click **No** then **Yes** to discard: all pending operations are removed
- After recovery, re-run your import to process remaining files

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
- Use Photo Review app to fix dates and reorganize files
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

## Recovering from Data or Storage Corruption

This section provides comprehensive guidance for recovering from various corruption scenarios. While PyPhotoOrganizer includes multiple layers of protection, storage failures, power outages, and other issues can still cause problems. This guide covers detection, recovery, and prevention for all types of data corruption.

### Quick Reference: What Was Corrupted?

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "File is not a database" error | Database corruption | [Automatic Recovery](#database-corruption-automatic-recovery) |
| "Disk I/O error" during import | Database or disk issue | [Database Corruption](#database-corruption-automatic-recovery) |
| Photos missing from archive | Archive corruption or accidental deletion | [Archive Corruption](#archive-corruption) |
| Backup operation fails | Backup location corruption | [Backup Location Corruption](#backup-location-corruption) |
| Can't restore deleted files | Delete Vault corruption | [Delete Vault Corruption](#delete-vault-corruption) |
| Original versions missing | Prior Revision Archive corruption | [Prior Revision Archive Corruption](#prior-revision-archive-corruption) |
| Duplicate/conflicted files appear | Cloud sync conflict | [Cloud Sync Conflicts](#cloud-sync-conflicts) |

---

### Database Corruption (Automatic Recovery)

PyPhotoOrganizer now includes **automatic database corruption recovery**. When you attempt to open a corrupted database, the system will detect the problem and offer to restore from the most recent valid backup.

#### What Triggers Automatic Recovery

The system detects corruption when it encounters these errors:
- "File is not a database"
- "Disk I/O error"
- "Database disk image is malformed"
- "Database or disk is full"
- "Unable to open database"

#### Automatic Recovery Process

When corruption is detected, the following happens automatically:

1. **Backup Detection**: The system scans the `db_snapshots/` directory for available backups
2. **Backup Validation**: Each backup is tested with SQLite integrity checks until a valid one is found
3. **User Confirmation**: A dialog shows:
   - When the backup was created
   - Why it was created (e.g., "pre import")
   - How many photos are in the backup
   - The backup file size

4. **Restoration**: If you confirm:
   - The corrupted database is renamed with `.corrupted_TIMESTAMP` suffix
   - The backup is copied to the original location
   - Any leftover WAL/SHM files are cleaned up

5. **Orphaned File Recovery**: After restoration, you're offered an **archive scan** to recover files that were imported after the backup was created:
   - The system scans your entire archive
   - Files not in the restored database are identified as "orphaned"
   - Orphaned files are added back to the database with recovery metadata
   - You can view recovered files in Import History under "Archive Recovery" filter

#### Example Recovery Dialog

```
Database Corruption Detected

The database file is corrupted and cannot be opened.

Error: Not a valid SQLite database: file is not a database

A backup is available:
  • Created: 2024-01-15 at 14:30:22
  • Reason: pre import
  • Photos: 66,709
  • Size: 197.0 MB

Would you like to restore from this backup?

The corrupted file will be renamed with a .corrupted suffix.

[Yes] [No]
```

#### After Recovery

After the database is restored and the archive scan completes:

- **Immediately Available**: All photos from the backup, plus any recovered orphaned files
- **Lost Data**: Import history and audit logs from after the backup
- **Preserved**: All photos in your archive (files are never deleted)
- **Recoverable**: Files imported after the backup (via archive scan)

#### Viewing Recovered Files

To see files that were recovered during the archive scan:

1. Open **Import History** tab
2. In the **Show** dropdown, select **"Archive Recovery"**
3. All files recovered from the archive scan are listed

Recovered files have these markers in the database:
- `source_path` starts with `RECOVERED:`
- `revision_reason` is `recovered_from_archive`

#### Manual Database Recovery

If automatic recovery doesn't appear or you prefer manual control:

1. **Close PyPhotoOrganizer** completely
2. **Navigate to your database directory**
3. **Find the `db_snapshots` folder**
4. **Copy the most recent valid backup** over your corrupted database:
   ```bash
   # Linux/macOS
   cp db_snapshots/db_snapshot_20240115_143022_pre_import_a1b2c3d4.db PhotoDB.db

   # Windows
   copy db_snapshots\db_snapshot_20240115_143022_pre_import_a1b2c3d4.db PhotoDB.db
   ```
5. **Delete WAL/SHM files** if present:
   ```bash
   rm PhotoDB.db-wal PhotoDB.db-shm
   ```
6. **Restart PyPhotoOrganizer**

---

### Archive Corruption

If files in your photo archive become corrupted or are accidentally deleted:

#### Symptoms
- Photos display incorrectly or won't open
- "File not found" errors in Photo Review
- Missing thumbnails
- Gaps in your photo timeline

#### Recovery Options

**Option 1: Restore from External Backup**

If you maintain external backups of your archive (highly recommended):

1. Identify the corrupted/missing files from Import History
2. Restore those files from your backup to the same locations in the archive
3. The database already has the correct paths, so files will be recognized immediately

**Option 2: Re-import from Original Sources**

If you still have the original source files:

1. Ensure source directories are configured in Import Settings
2. Run a new import - the system will:
   - Skip files that already exist in the archive (by hash)
   - Re-import any missing files
   - Place them in the correct date-based folders

**Option 3: Recover from Prior Revision Archive**

If the corrupted files have prior revisions (from rotations or edits):

1. Open **Photo Review**
2. Find the affected photo
3. Check if prior revisions exist
4. Restore from a prior revision if available

**Option 4: Recover from Delete Vault**

If files were accidentally deleted and are in the Delete Vault:

1. Go to **Archive Maintenance** tab
2. Click **"View Vault Contents"**
3. Select the files you want to restore
4. Click **"Restore Selected"**

#### Preventing Archive Corruption

1. **Use reliable storage**: Enterprise SSDs or quality HDDs
2. **Maintain multiple backups**: Follow the 3-2-1 rule (3 copies, 2 media types, 1 offsite)
3. **Enable content hashing**: Helps detect visual duplicates even if file hashes change
4. **Avoid editing directly in archive**: Use Photo Review for rotations/edits
5. **Monitor disk health**: Use tools like CrystalDiskInfo (Windows) or smartctl (Linux)

---

### Backup Location Corruption

The configured backup location (set in Archive Maintenance) stores full database backups.

#### Symptoms
- "Backup failed" errors
- Cannot create scheduled backups
- Backup directory inaccessible

#### Recovery Steps

1. **Check if backup location exists**:
   - Navigate to the configured backup path
   - If the drive/folder is missing, restore it or choose a new location

2. **Configure a new backup location**:
   - Go to **Archive Maintenance** tab
   - Click **"Change"** next to Backup Location
   - Select a new, accessible folder
   - Create a new backup immediately

3. **Recover from previous backups**:
   - Check other locations where you may have manual backups
   - The `db_snapshots/` folder (next to your database) always has recent snapshots

#### Best Practices

- Don't place backups on the same drive as your database
- Use a separate physical drive or network location
- Verify backups periodically by listing their contents

---

### Delete Vault Corruption

The Delete Vault stores soft-deleted files for potential recovery.

#### Symptoms
- Cannot restore deleted files
- "File not found" when attempting restore
- Vault contents don't match database records

#### Recovery Steps

1. **Check vault location**:
   - Go to **Archive Maintenance** tab
   - Verify the Delete Vault path is accessible

2. **If vault files are missing but database records exist**:
   - The files are unrecoverable from the vault
   - Check if you have external backups
   - The original source files may still exist

3. **If vault is completely corrupted**:
   - Configure a new Delete Vault location
   - Existing vault records will show files as "unrecoverable"
   - New deletions will use the new vault

4. **Clean up orphaned records**:
   - If vault files exist but records are corrupted
   - You may need to manually re-import these files
   - They'll be treated as new files with new database entries

---

### Prior Revision Archive Corruption

The Prior Revision Archive stores original versions of files before rotation or editing.

#### Symptoms
- Cannot undo rotations/edits
- "Original not found" errors
- Prior Revision Archive directory missing

#### Recovery Steps

1. **If the archive directory is missing**:
   - Reconfigure the Prior Revision Archive location
   - Previous revisions are lost, but current versions are intact

2. **If specific revision files are corrupted**:
   - The current archive version is still valid
   - Undo functionality for those files is lost
   - Future edits will create new revision backups

3. **Rebuilding revision tracking**:
   - If you have external backups of the Prior Revision Archive
   - Restore the files to the configured location
   - The database links (by file hash) should reconnect automatically

#### Minimizing Impact

- The Prior Revision Archive is for convenience, not critical data
- Your main archive always has the current (edited) version
- Consider including Prior Revision Archive in your backup strategy if undo is important to you

---

### Cloud Sync Conflicts

Using cloud-synced folders (Dropbox, OneDrive, Google Drive, iCloud) for your database can cause corruption due to sync conflicts.

#### Symptoms
- "File is not a database" error after sync
- Duplicate files with "(1)" or "conflicted copy" suffixes
- Random corruption during imports
- Different data on different computers

#### Why This Happens

SQLite databases use multiple files (`.db`, `.db-wal`, `.db-shm`) that must stay synchronized. Cloud services may:
- Sync the main file before the WAL file
- Create conflicts when two devices access simultaneously
- Interrupt writes during sync operations

#### Immediate Recovery

1. **Stop all PyPhotoOrganizer instances** on all devices
2. **Wait for sync to complete** on all devices
3. **Identify the correct version**:
   - Check file dates
   - Look for conflict copies
   - Choose the most recent valid database
4. **Use automatic recovery** to restore from backup if needed
5. **Delete conflict copies** after recovery

#### Recommended Configuration

**Option 1: Local Database, Synced Archive (Recommended)**
```
Database:  C:\Users\You\Documents\PhotoDB.db        (local, not synced)
Archive:   D:\Dropbox\PhotoArchive\                 (synced for backup)
```

**Option 2: Synced Database with Precautions**
```
Database:  D:\Dropbox\PhotoDB.db                    (synced - risky)
Archive:   D:\Dropbox\PhotoArchive\                 (synced)

Precautions:
- Only run PyPhotoOrganizer on ONE device at a time
- Wait for sync to complete before switching devices
- Pause sync during large imports
- Keep extra backups outside cloud storage
```

**Option 3: Network Database (Advanced)**
```
Database:  \\NAS\Photos\PhotoDB.db                  (network share)
Archive:   \\NAS\Photos\Archive\                    (network share)

Notes:
- Slower but avoids sync conflicts
- Use on local network only
- Ensure stable connection
```

#### Preventing Cloud Sync Issues

1. **Pause sync during imports**: Use your cloud client's pause feature
2. **One device at a time**: Never run PyPhotoOrganizer simultaneously on multiple devices
3. **Wait for sync**: Ensure uploads complete before switching devices
4. **Local database**: Keep the `.db` file outside synced folders when possible
5. **Regular backups**: Export to a non-synced location regularly

---

### Disk and Storage Failures

Complete disk failure requires restoring from backups.

#### Symptoms
- Drive not recognized by system
- Clicking/grinding noises from HDD
- Massive I/O errors in logs
- System crashes when accessing drive

#### If the Database Drive Failed

1. **Replace the failed drive**
2. **Restore database from**:
   - Last known good backup from another location
   - Cloud backup if configured
   - Another computer if synced
3. **Use automatic recovery** if backup is partial/old

#### If the Archive Drive Failed

1. **Replace the failed drive**
2. **Restore archive from your external backup**
3. **Database will still work** - paths will show files as missing until restored
4. **Re-import from sources** if no archive backup exists

#### If Multiple Drives Failed

1. Prioritize restoring the archive (your actual photos)
2. Database can be rebuilt from archive if needed:
   - Create new database
   - Add archive as source folder
   - Run import to rebuild database from archive files

#### Building Resilience

1. **RAID arrays**: For archive storage (RAID 1 or RAID 5)
2. **UPS**: Prevent corruption from power loss
3. **Regular backups**: Test restores periodically
4. **Monitor drive health**: Replace drives showing SMART warnings
5. **Geographic distribution**: Keep one backup offsite

---

### Complete Disaster Recovery Checklist

Use this checklist when recovering from a major failure:

#### Phase 1: Assessment
- [ ] Identify what was lost (database, archive, both)
- [ ] Locate all available backups
- [ ] Check cloud storage for synced copies
- [ ] Verify source files still exist (if re-import needed)

#### Phase 2: Database Recovery
- [ ] Restore database from most recent backup
- [ ] Use automatic recovery if database is corrupted
- [ ] Run archive scan to recover orphaned files
- [ ] Verify database opens without errors
- [ ] Check photo count matches expectations

#### Phase 3: Archive Recovery
- [ ] Restore archive files from backup
- [ ] Verify restored files are accessible
- [ ] Run Photo Review to spot-check images
- [ ] Re-import from sources if files are missing

#### Phase 4: Validation
- [ ] Open Photo Review and browse archive
- [ ] Check Import History for recent sessions
- [ ] Verify albums contain expected photos
- [ ] Test a few operations (rotation, deletion, restore)

#### Phase 5: Prevention
- [ ] Review and improve backup strategy
- [ ] Consider additional redundancy
- [ ] Document your recovery process
- [ ] Schedule regular backup verification

---

### Prevention Best Practices Summary

| Practice | Protects Against | Implementation |
|----------|------------------|----------------|
| Automatic snapshots | Database corruption | Enabled by default before imports |
| Manual backups | All data loss | Copy .db file weekly to external drive |
| Archive backups | Archive corruption | Full backup to external drive monthly |
| Content hashing | Visual duplicate detection | Enable in System Settings |
| Local database | Cloud sync conflicts | Store .db outside synced folders |
| UPS | Power loss corruption | Connect computer to UPS |
| SMART monitoring | Drive failure | Use disk health monitoring tools |
| 3-2-1 backups | Complete disaster | 3 copies, 2 media types, 1 offsite |

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
**A:** The application creates automatic snapshots in `db_snapshots/` before each import. For additional safety, copy the `.db` file to a safe location periodically. The archive folder should also be backed up separately.

### Q: My database is corrupted. How do I recover?
**A:** PyPhotoOrganizer now includes **automatic recovery**. When you try to open a corrupted database:
1. The system automatically detects the corruption
2. It finds the most recent valid backup in `db_snapshots/`
3. A dialog offers to restore from that backup
4. After restoration, it offers to scan the archive for any files imported since the backup

See the comprehensive [Recovering from Data or Storage Corruption](#recovering-from-data-or-storage-corruption) section for detailed guidance on all corruption scenarios.

### Q: The application crashed during an import. Did I lose data?
**A:** No. On next startup, the application detects incomplete operations and offers to recover them. Files that were successfully copied are preserved, and partially-copied files are cleaned up. You can then re-run the import to continue where it left off.

### Q: Can I change the archive location?
**A:** Yes! Starting with version 3.4, the database stores relative paths which makes it portable. If you move your archive:
1. Move the archive files to the new location
2. Open the database in PyPhotoOrganizer
3. Go to Archive Settings and update the archive location to the new path
4. The database will automatically resolve all paths using the new location

For databases created before v3.4, run the migration first:
```bash
python -m migrations.schema_v6_relative_paths /path/to/PhotoDB.db
```

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
| 3.0.3 | Prior Revision Archive system |
| 3.3 | Content-based duplicate detection |
| 3.4 | Relative path storage for archive portability |
| 3.4 | Archive Change Detection for external modifications |
| 3.5 | Database health checks, automatic backups, crash recovery, copy verification |
| 3.6 | Bulk Delete Matching Files for removing archive files that match a reference folder |

---

*PyPhotoOrganizer - Organize your memories, eliminate duplicates.*
