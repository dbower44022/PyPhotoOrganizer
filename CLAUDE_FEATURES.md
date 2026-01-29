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

## Video Content-Based (Perceptual) Hashing (Schema v9)

Detects visually identical videos even when re-encoded, transcoded, or with different metadata.

### Overview

- **Default:** Enabled (configurable in System Settings)
- **Dependency:** `imagehash>=4.3.1` for perceptual hashing
- **Requirement:** `ffmpeg` for frame extraction
- **Storage:** `UniquePhotos.video_content_hash`

### Algorithm

Two-stage approach for efficiency:

1. **Quick Filter** (future enhancement): Duration (±1s) + Resolution match
2. **Visual Comparison**: Extract 5 frames → pHash each → combine into signature

```python
def hash_video_content(file_path):
    # Extract 5 frames at 10%, 30%, 50%, 70%, 90% of duration
    extractor = VideoThumbnailExtractor()
    metadata = extractor.get_video_metadata(file_path)

    frame_hashes = []
    for timestamp_pct in [0.10, 0.30, 0.50, 0.70, 0.90]:
        timestamp = metadata.duration * timestamp_pct
        frame = extractor.extract_thumbnail_pil(file_path, size=64, timestamp=timestamp)
        frame = frame.convert('L')  # Grayscale
        phash = imagehash.phash(frame)
        frame_hashes.append(str(phash))

    # Combine and hash
    combined = '|'.join(frame_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()
```

### Key Behaviors

- Returns `None` for images (videos only)
- Returns `None` if ffmpeg not available (graceful degradation)
- Requires at least 3 frames for valid signature
- Skips videos shorter than 1 second
- Uses `VideoThumbnailExtractor` from `video_thumbnail.py`

### Configuration Constants (`constants.py`)

| Constant | Default | Description |
|----------|---------|-------------|
| `VIDEO_CONTENT_HASH_FRAME_COUNT` | 5 | Frames to extract |
| `VIDEO_CONTENT_HASH_TIMESTAMPS` | [0.10, 0.30, 0.50, 0.70, 0.90] | Extraction points |
| `VIDEO_CONTENT_HASH_FRAME_SIZE` | 64 | Frame resize (NxN) |
| `VIDEO_CONTENT_HASH_DURATION_TOLERANCE` | 1.0 | Duration match tolerance (seconds) |
| `VIDEO_CONTENT_HASH_EXTRACTION_TIMEOUT` | 30 | Timeout per frame (seconds) |

### Database Methods (PhotoDatabase)

- `has_video_content_hash(video_content_hash)` - Check existence
- `get_files_by_video_content_hash(video_content_hash)` - Get matching files
- `update_video_content_hash(file_hash, video_content_hash)` - Update record
- `get_videos_without_content_hash(limit)` - For backfill (default limit: 50)
- `count_videos_without_content_hash()` - Progress display

### Settings (DatabaseMetadata)

- `is_video_content_hash_enabled()` - Check if enabled (default: true)
- `set_video_content_hash_enabled(enabled)` - Toggle

### UI Integration

- **System Settings**: Enable checkbox + "Calculate Video Content Hashes for Existing Files" button
- **Import History**: "Video Content Duplicates" filter (magenta-purple #CC6699)
- **Audit Logging**: Operation `'video_content_duplicate_detected'`, status `'video_content_duplicate'`

### Backfill Worker

`VideoContentHashBackfillWorker` (`ui/video_content_hash_worker.py`):

| Signal | Parameters | Description |
|--------|------------|-------------|
| `progress_update` | current, total, filename | Progress update |
| `status_update` | message | Status text |
| `completed` | dict (results) | Backfill finished |
| `error_occurred` | error_msg | Critical error |

**Results dict keys:** `status`, `files_processed`, `files_updated`, `files_skipped`, `files_failed`, `discovered_duplicates`, `was_cancelled`

### Error Handling

- **imagehash not installed**: Log warning, skip video content hashing, import continues
- **ffmpeg not available**: Log debug, return None, import continues
- **Frame extraction fails**: Return None, file processed without video content hash
- **Database errors**: Log error, don't crash import

### Performance Notes

- Batch size: 50 videos (lower than images due to higher processing cost)
- Memory: ~20KB per video (5 × 64×64 grayscale frames)
- Frame extraction: Uses existing `VideoThumbnailExtractor` (ffmpeg)

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

---

## Cloud Storage (Schema v8)

Store archive files in cloud storage services like Amazon S3.

### Overview

- **Default:** Disabled (local storage)
- **Providers:** Amazon S3 (Azure, GCS planned)
- **Per-vault:** Each vault can have different storage configuration
- **Sync:** Manual or automatic sync to cloud

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
├─────────────────────────────────────────────────────────────┤
│  CloudSync          │  CloudSyncManager   │  UI Widgets     │
│  (orchestration)    │  (upload queue)     │  (configuration)│
├─────────────────────────────────────────────────────────────┤
│                    StorageManager                            │
│              (multi-vault backend management)                │
├─────────────────────────────────────────────────────────────┤
│  LocalStorageBackend │  S3StorageBackend  │  (Future: Azure)│
├─────────────────────────────────────────────────────────────┤
│      Local FS        │     boto3/S3       │  azure-storage  │
└─────────────────────────────────────────────────────────────┘
```

### Storage Backend Abstraction

All storage operations go through `StorageBackend` ABC:

```python
class StorageBackend(ABC):
    @abstractmethod
    def exists(self, path: str) -> bool: ...
    @abstractmethod
    def read_file(self, path: str) -> bytes: ...
    @abstractmethod
    def write_file(self, path: str, data: bytes) -> bool: ...
    @abstractmethod
    def copy_from_local(self, local_path: str, remote_path: str) -> bool: ...
    @abstractmethod
    def copy_to_local(self, remote_path: str, local_path: str) -> bool: ...
    @abstractmethod
    def compute_hash(self, path: str, algorithm: str = 'sha256') -> str: ...
```

### Key Classes

| Class | Module | Purpose |
|-------|--------|---------|
| `StorageBackend` | `storage_backend.py` | Abstract interface for storage |
| `LocalStorageBackend` | `storage_backend.py` | Local filesystem implementation |
| `StorageProviderRegistry` | `storage_backend.py` | Factory for creating backends |
| `StorageManager` | `storage_backend.py` | Multi-vault management |
| `S3StorageBackend` | `storage_backend_s3.py` | Amazon S3 implementation |
| `CloudSyncManager` | `cloud_sync_manager.py` | Upload queue, retry logic |
| `CloudSync` | `cloud_sync.py` | High-level sync operations |
| `CloudSyncWorker` | `ui/cloud_sync_worker.py` | Background sync thread |
| `CloudSettingsWidget` | `ui/cloud_settings_widget.py` | Per-vault UI config |

### S3 Features

- **Multipart upload** for files >8MB
- **Storage classes**: STANDARD, INTELLIGENT_TIERING, GLACIER, etc.
- **Retry logic** with exponential backoff
- **Hash verification** after upload
- **Presigned URLs** for temporary access

### Database Tables (Schema v8)

| Table | Purpose |
|-------|---------|
| `CloudSyncStatus` | Track upload status per file/vault |
| `FileLocations` | Track file locations (local + cloud) |
| `CloudUploadQueue` | Pending uploads with retry support |

### Configuration Storage

Storage config in `DatabaseMetadata.storage_config` (JSON):

```json
{
  "archive": {
    "provider": "s3",
    "bucket": "my-photos",
    "prefix": "archive",
    "region": "us-east-1",
    "storage_class": "INTELLIGENT_TIERING"
  },
  "video_archive": {
    "provider": "local",
    "path": "/mnt/videos"
  }
}
```

### Sync Operations

| Operation | Class | Method |
|-----------|-------|--------|
| Find unsynced files | `CloudSync` | `find_files_needing_upload()` |
| Sync vault to cloud | `CloudSync` | `sync_vault_to_cloud()` |
| Download from cloud | `CloudSync` | `download_from_cloud()` |
| Queue single file | `CloudSyncManager` | `queue_upload()` |
| Process queue | `CloudSyncManager` | `process_queue()` |
| Check sync status | `CloudSync` | `get_sync_status_summary()` |

### Conflict Resolution

When local and cloud differ:

```python
class ConflictResolution(Enum):
    KEEP_LOCAL = 'keep_local'    # Upload local version
    KEEP_CLOUD = 'keep_cloud'    # Download cloud version
    KEEP_BOTH = 'keep_both'      # Keep both (rename one)
    SKIP = 'skip'                # Skip this file
    ASK = 'ask'                  # Ask user
```

### Worker Signals

`CloudSyncWorker` emits:

| Signal | Parameters | Description |
|--------|------------|-------------|
| `progress` | `SyncProgress` | Progress update |
| `file_completed` | `file_hash, success, error` | Single file done |
| `sync_completed` | `dict` (stats) | Sync finished |
| `error` | `str` (message) | Critical error |
| `paused` | - | Sync paused |
| `resumed` | - | Sync resumed |

### Key Gotchas

1. **boto3 optional** - S3 features only work if boto3 installed
2. **AWS credentials** - Must be configured via CLI, env vars, or IAM role
3. **Local copy required** - Files must exist locally before cloud upload
4. **Hash verification** - Uses SHA-256, not S3's MD5 ETag
5. **Storage class transitions** - Use `set_storage_class()` for existing files
6. **Worker cleanup** - Must call `worker.request_stop()` and `worker.wait()` on close

### Testing

- Unit tests: `tests/unit/test_storage_backend.py` (50 tests)
- S3 tests: `tests/unit/test_storage_backend_s3.py` (uses moto mock)
- Sync tests: `tests/unit/test_cloud_sync.py` (12 tests)
