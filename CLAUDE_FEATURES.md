# CLAUDE_FEATURES.md

Detailed implementation documentation for complex features in PyPhotoOrganizer.

**See also:** [CLAUDE.md](CLAUDE.md) for core project guidelines.

---

## Metadata-Based Archive Upgrades (Schema v7)

Intelligently upgrades archive files when importing duplicates with better metadata.

### Overview

- **Default:** Enabled (configurable in System Settings)
- **Trigger:** Incoming duplicate has better metadata quality than archive file
- **Protection:** User-corrected files are never replaced
- **Preservation:** Original always saved to Prior Revision Archive

### Metadata Quality Scoring (0-100)

| Date Source | Base Score | Description |
|-------------|------------|-------------|
| `exif` | 80 | DateTimeOriginal (best) |
| `exif_digitized` | 70 | DateTimeDigitized |
| `exif_gps` | 65 | GPS timestamp |
| `video_metadata` | 60 | ffprobe/mutagen |
| `video_quicktime` | 55 | QuickTime atoms |
| `exif_datetime` | 50 | DateTime (modification) |
| `exif_preview` | 45 | PreviewDateTime |
| `iptc` | 40 | IPTC Date Created |
| `os_metadata` | 20 | OS timestamps |
| `fallback` | 0 | Year 1000 fallback |

**Reliability bonus:** +20 if date is reliable (not flagged suspicious).

### Upgrade Decision

Incoming replaces archive if:
1. Higher quality score, OR
2. Same score AND incoming reliable AND archive not

### User Protection

Files protected from replacement if:
- `revision_reason` is `'date_correction'`, `'exif_edit'`, or `'manual_correction'`
- Has `corrected_date` in `UnreliableDates` table
- Any ancestor in revision chain was user-edited

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `calculate_metadata_quality_score()` | `DuplicateFileDetection.py` | Compute 0-100 score |
| `should_upgrade_archive_file()` | `DuplicateFileDetection.py` | Compare and decide |
| `is_file_manually_corrected()` | `DuplicateFileDetection.py` | Check user protection |
| `perform_metadata_upgrades()` | `main.py` | Execute upgrades |

### Processing Flow

1. `find_duplicates()` detects duplicate
2. If enabled: check metadata quality, check protection
3. If upgrade warranted: add to `upgrade_candidates`
4. After organizing: `perform_metadata_upgrades()` processes candidates

### Results Keys

**find_duplicates():** `upgrade_candidates`, `protected_files`

**organize_files():** `upgrade_candidates`, `upgrades_completed`, `upgrades_failed`, `upgrades_skipped`, `protected_files`, `files_reorganized`

---

## Content-Based (Pixel) Hashing

Detects visually identical images with different file hashes (metadata changes).

### Algorithm

```python
def hash_image_content(file_path):
    with Image.open(file_path) as img:
        img = ImageOps.exif_transpose(img)  # Apply EXIF rotation
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return hashlib.sha256(img.tobytes()).hexdigest()
```

### Key Behaviors

- Returns `None` for videos (images only)
- Applies EXIF rotation before hashing
- Converts to RGB for consistency
- Stored in `UniquePhotos.content_hash`

### Database Methods (PhotoDatabase)

- `has_content_hash(content_hash)` - Check existence
- `get_files_by_content_hash(content_hash)` - Get matching files
- `update_content_hash(file_hash, content_hash)` - Update record
- `get_files_without_content_hash(limit)` - For backfill
- `count_files_without_content_hash()` - Progress display

### Settings (DatabaseMetadata)

- `is_content_hash_enabled()` - Check if enabled (default: true)
- `set_content_hash_enabled(enabled)` - Toggle

### UI Integration

- System Settings: Enable checkbox + "Calculate Content Hashes" button
- Import History: "Content Duplicates" filter (purple #9966CC)
- Photo Review: "Content Duplicates" view filter

---

## Override Skip Feature

Import files previously filtered out (skipped due to size/dimensions).

### Flow

1. User selects `operation='skip_filtered'` rows in Import History
2. Click "Override Skip" → validation → confirmation dialog
3. Yellow highlight on processing rows
4. `ReprocessWorker` imports directly (bypasses PhotoFilter)
5. Rows removed in real-time as each completes
6. Files added to albums if source has association

### UI Features

| Feature | Description |
|---------|-------------|
| Select All Visible | Select all rows in current view |
| Override Skip | Import selected filtered files |
| Undo Override | Delete files, remove DB entries, restore rows |
| Recently Overridden filter | View files imported via Override Skip |

### Key Methods (ImportHistoryTab)

- `override_skip_files()` - Main handler
- `_on_override_skip_file_processed()` - Real-time row removal
- `_on_override_skip_completed()` - Cleanup, undo state
- `undo_last_override_skip()` - Reverse operation
- `_select_all_visible()` - Select all in view

### FileLogTableModel Methods

- `removeRowsBySourcePath(paths)` - Remove matching rows
- `markRowsAsProcessing(paths)` - Yellow highlight
- `clearProcessingFlags()` - Clear visual state

---

## Archive Change Detection

Detects external modifications to archive files.

### How It Works

1. User selects scope (entire archive or folder)
2. Compare current content hash vs. stored value
3. On mismatch:
   - Original copied to Prior Revision Archive
   - Revision record created
   - Logged as `'external_modification_detected'`

### Prerequisites

- Database loaded
- Prior Revision Archive configured (required)
- Files have content hashes

### UI Location

Archive Maintenance tab → "Archive Change Detection" group

### Audit Logging

- Operation: `'external_modification_detected'`
- Status: `'revision_created'`, `'original_not_found'`, `'failed'`
- Filter: "External Modifications"

---

## Bulk Delete Matching Files

Delete archive files matching files in a reference folder.

### Two-Phase Operation

1. **Scan:** Hash reference folder files, match against archive
2. **Delete:** Soft-delete matches (move to Delete Vault)

### Preview Dialog

- Tab 1: Matched files (to be deleted)
- Tab 2: Not-found files (not in archive)
- Summary: matches, not found, total size

### Deletion Process

1. Validate file is in archive (not source)
2. Copy to Delete Vault preserving structure
3. Verify copy (exists + size matches)
4. Delete from archive
5. `mark_file_as_deleted()` - DeletedFiles record
6. `sync_deletion_to_albums()` - Remove from albums
7. Remove from UnreliableDates
8. Clean up empty directories
9. Log to audit trail

### UI Location

Archive Maintenance tab → "Bulk Delete Matching Files" group

### Undo

Files soft-deleted to vault, restorable via "View Vault Contents" → "Restore Selected".

---

## Source Directory Album Association

Automatic album population during import.

### Database Columns (SourceDirectories)

- `album_id` - FK to Albums.id (NULL = no association)
- `enable_sub_albums` - 0=disabled, 1=create sub-albums

### Import Flow

For each file copied to archive:
1. Find matching source directory
2. If sub-albums disabled: add to parent album
3. If sub-albums enabled AND in subdirectory:
   - Name: `"{Parent} - {Subdir1} - {Subdir2}"`
   - Storage: `parent_storage/{relative_subdir}/`
   - Track in `SourceDirectorySubAlbums`
4. Copy to album via `AlbumManager.add_photo_to_album()`

### Sub-Album Examples

| Source | File Location | Sub-Album Name |
|--------|---------------|----------------|
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/Camera/pic.jpg` | "Phone - Camera" |
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/WhatsApp/Media/img.jpg` | "Phone - WhatsApp - Media" |

### Key Methods

| Location | Method |
|----------|--------|
| `database_metadata.py` | `update_source_album()`, `update_source_sub_albums_enabled()`, `get_or_create_sub_album()` |
| `import_settings_tab.py` | `get_source_album_mapping()`, `_create_new_album()` |
| `album_manager.py` | `add_photo_to_album()` |

### Error Handling

Album failures are non-fatal (logged, import continues).

---

## Source Directory Path Validation

Validates paths with detailed diagnostics.

### Validation Checks

1. `os.path.exists(path)` - Must exist
2. `os.path.isdir(path)` - Must be directory
3. `os.access(path, os.R_OK)` - Must have read permission

### Network Mount Detection

Recognizes and provides guidance for:
- NFS: paths containing `-nfs` or `/nfs/`
- SMB/CIFS: paths containing `-smb`, `-cifs`
- GVFS: paths starting with `/run/user/*/gvfs/`
- Generic: paths under `/mnt/` or `/media/`

### Path Break Detection

When path doesn't exist, identifies where it breaks:
```
Path breaks at: /data/NAS-nfs/Photos
Last valid path: /data/NAS-nfs
```

### OS Error Handling

| Error | Guidance |
|-------|----------|
| `ESTALE` | NFS handle stale, remount needed |
| `ETIMEDOUT` | Network share not responding |
| `EHOSTUNREACH` | Network connectivity issue |

### Diagnostic Methods

- `_diagnose_missing_path()` - Where path breaks, mount types
- `_diagnose_permission_error()` - Permission guidance
- `_diagnose_os_error()` - OS-level errors

### UI

- ✓ green = valid, ⚠ red = invalid
- Hover for diagnostic tooltip
- "Refresh Status" to re-validate

---

## Orphaned File Recovery

Recover files after database restore that were imported after backup.

### When Offered

After successful backup restoration.

### Flow

1. `ArchiveRecoveryWorker` scans archive for media files
2. Hash each file, check against database
3. Files not in database are "orphaned"
4. Add to database with recovery metadata

### Recovery Metadata

- `source_path` = `RECOVERED:<original_archive_path>`
- `revision_reason` = `recovered_from_archive`

### Audit

- Session: `operation_mode='archive_recovery'`
- Operation: `'archive_recovery'`
- Filter: "Archive Recovery"
