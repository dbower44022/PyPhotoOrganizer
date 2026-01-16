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
10. [File Version Management](#file-version-management)
11. [Photo Review App](#photo-review-app)
12. [Import History](#import-history)
13. [Settings](#settings)
14. [Troubleshooting](#troubleshooting)
15. [FAQ](#faq)

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

1. Select rotated file in Date Corrections tab
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
Use Date Corrections tab comments/notes to record:
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
- **Show dropdown**: Filter by All Files, New Files, Duplicates, Filtered, or Errors
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
