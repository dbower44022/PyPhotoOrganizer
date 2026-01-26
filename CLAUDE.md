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
| `path_resolver.py` | `PathResolver`: resolves relative paths to absolute using archive base locations (Schema v6) |

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
| `bulk_delete_worker.py` | `BulkDeleteWorker` for bulk delete matching files operations |
| `bulk_delete_preview_dialog.py` | `BulkDeletePreviewDialog` for previewing matched files before deletion |
| `archive_recovery_worker.py` | `ArchiveRecoveryWorker` for recovering orphaned files after database restore |
| `theme.py` | `ThemeManager`, light/dark mode support |

### Database Tables

All tables in SQLite database (default: `PhotoDB.db`):

| Table | Purpose |
|-------|---------|
| `DatabaseMetadata` | Archive location, settings, schema version |
| `UniquePhotos` | File hashes, paths, creation dates, revision tracking, content_hash, relative_path, storage_type (Schema v6) |
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

**Note (Schema v6):** Added relative path storage for archive portability. New columns `relative_path` (path relative to archive base) and `storage_type` ('archive', 'video_archive', or 'prior_revision') enable databases to work when archives are moved. Related tables also have relative path columns: `AlbumPhotos.relative_album_path`, `DeletedFiles.relative_archive_path/relative_vault_path/archive_storage_type`, `UnreliableDates.relative_archive_path`.

### Database Connection Pattern

All modules use WAL mode for concurrent access:
```python
conn = sqlite3.connect(path, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
```

### Database Auto-Upgrade

`DatabaseMetadata._ensure_metadata_table()` and similar methods automatically add missing columns/tables on first access using `ALTER TABLE ... ADD COLUMN`. No manual migrations needed.

### Database Health, Backup, and Recovery System

The application includes comprehensive data integrity features for crash recovery, automatic backups, and health monitoring.

#### New Database Tables

| Table | Purpose |
|-------|---------|
| `PendingOperations` | Tracks in-flight copy/move operations for crash recovery |
| `AuditQueue` | Queues failed audit log entries for retry |
| `QuickBackups` | Tracks rolling database snapshots |

**PendingOperations Schema:**
```sql
CREATE TABLE PendingOperations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT UNIQUE NOT NULL,  -- UUID for this operation
    operation_type TEXT NOT NULL,        -- 'copy' or 'move'
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL,                -- 'pending', 'copied', 'verified', 'committed', 'failed'
    created_timestamp TEXT NOT NULL,
    error_message TEXT
);
```

**AuditQueue Schema:**
```sql
CREATE TABLE AuditQueue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_timestamp TEXT NOT NULL,
    log_type TEXT NOT NULL,              -- 'unreliable_date', 'file_operation', etc.
    payload_json TEXT NOT NULL,          -- JSON-serialized audit data
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
);
```

**QuickBackups Schema:**
```sql
CREATE TABLE QuickBackups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_path TEXT NOT NULL,
    backup_reason TEXT NOT NULL,         -- 'pre_import', 'pre_batch_edit', 'auto'
    created_timestamp TEXT NOT NULL,
    database_size_bytes INTEGER,
    is_valid INTEGER DEFAULT 1
);
```

#### Copy Verification

After copy/move operations, file integrity is verified by re-hashing:

```python
def verify_copy_integrity(dest_path: str, expected_hash: str, retry_count: int = 1) -> tuple:
    """
    Verify that a copied file matches the expected hash.

    Returns:
        tuple: (verified: bool, actual_hash: str, error_message: str or None)
    """
```

**Integration in `organize_files()`:**
1. Create pending operation record BEFORE copy
2. Perform copy/move operation
3. Update status to 'copied'
4. Verify hash matches expected
5. Update status to 'verified' or 'failed'
6. On database commit success, delete pending operation

#### Pending Operations (Crash Recovery)

**Purpose:** Track operations that span multiple steps (copy → verify → database commit) so interrupted operations can be recovered.

**Status Flow:**
```
pending → copied → verified → (database commit) → delete record
                           ↘ failed (on verification failure)
```

**Key Methods (DatabaseMetadata class):**
- `create_pending_operation()` - Record operation before starting
- `update_pending_status()` - Update status as operation progresses
- `get_incomplete_operations()` - Find operations needing recovery
- `delete_pending_operation()` - Remove after successful completion
- `cleanup_old_pending_operations(days_old)` - Remove stale records

**Recovery on Startup:**
```python
def _recover_pending_operations(self):
    """Recover incomplete operations from previous session."""
    pending = self.database_metadata.get_incomplete_operations()
    for op in pending:
        if op['status'] == 'verified':
            # Just needs database commit - mark recovered
            pass
        elif op['status'] == 'copied':
            # Verify the copy, clean up if corrupt
            verified, _, _ = verify_copy_integrity(op['target_path'], op['file_hash'])
            if not verified:
                os.remove(op['target_path'])  # Remove corrupt copy
        elif op['status'] in ('pending', 'failed'):
            # Clean up orphaned files
            if os.path.exists(op['target_path']):
                os.remove(op['target_path'])
        self.database_metadata.delete_pending_operation(op['operation_id'])
```

#### Quick Database Backups

**Purpose:** Create fast database-only snapshots before major operations.

**Key Methods (DatabaseMetadata class):**
- `create_quick_backup(reason)` - Create snapshot with reason tag
- `get_quick_backups()` - List available backups
- `restore_quick_backup(backup_id)` - Restore from a backup
- `_cleanup_old_quick_backups(keep_count)` - Maintain rolling window

**Backup Location:** `<database_directory>/db_snapshots/`

**Filename Format:** `db_snapshot_YYYYMMDD_HHMMSS_<reason>_<uuid8>.db`

**Rolling Retention:** Keeps last 5 snapshots, automatically deletes older ones.

**Pre-Import Backup:**
```python
def _create_pre_import_backup(self):
    """Create backup before starting import."""
    success, result = self.database_metadata.create_quick_backup(reason="pre_import")
```

#### Audit Queue (Retry System)

**Purpose:** Queue failed audit log entries for later retry instead of losing data.

**Key Methods (DatabaseMetadata class):**
- `queue_failed_audit(log_type, payload, error_message)` - Add to retry queue
- `get_queued_audits(limit)` - Get entries for processing
- `update_audit_queue_retry(queue_id, error_message)` - Increment retry count
- `delete_from_audit_queue(queue_id)` - Remove after success
- `get_audit_queue_count()` - Count pending entries
- `cleanup_audit_queue(max_retries, days_old)` - Remove exhausted/old entries
- `process_queued_unreliable_dates()` - Process queued unreliable date entries

**Retry Logic:**
- Max 5 retry attempts
- Entries older than 30 days are cleaned up
- Processed silently on startup

#### Database Health Check

**Purpose:** Detect and report database issues on startup.

```python
def check_database_health(self) -> Dict[str, Any]:
    """
    Run comprehensive health checks.

    Returns:
        {
            'healthy': bool,       # Overall health status
            'issues': [...],       # Critical problems
            'warnings': [...],     # Non-critical warnings
            'pending_ops': int,    # Operations needing recovery
            'wal_size_mb': float,  # WAL file size in MB
            'integrity_ok': bool   # PRAGMA integrity_check passed
        }
    """
```

**Checks Performed:**
1. SQLite `PRAGMA integrity_check` - Database corruption
2. Pending operations count - Crash recovery needed
3. WAL file size - Large WAL may indicate issues (warns >50MB)
4. Audit queue count - Failed entries awaiting retry

**WAL Management:**
- `_get_wal_size()` - Get WAL file size in bytes
- `checkpoint_wal(mode)` - Force WAL checkpoint (PASSIVE, FULL, RESTART, TRUNCATE)

#### Startup Health Check Flow

```python
def _run_startup_health_check(self):
    """Run on application startup."""
    health = self.database_metadata.check_database_health()

    # Critical issues - show error dialog
    if not health['healthy']:
        self._show_database_error_dialog(health['issues'])
        return

    # Pending operations - offer recovery
    if health['pending_ops'] > 0:
        self._offer_pending_recovery(health['pending_ops'])

    # Process queued audits silently
    self.database_metadata.process_queued_unreliable_dates()

    # Show warnings if any
    if health['warnings']:
        self._show_database_warning_dialog(health['warnings'])
```

#### UI Integration

**MainWindow (`ui/main_window.py`):**
- `_run_startup_health_check()` - Called when database is loaded
- `_show_database_error_dialog()` - Critical issue notification
- `_show_database_warning_dialog()` - Warning notification
- `_offer_pending_recovery()` - Recovery confirmation dialog
- `_recover_pending_operations()` - Perform recovery
- `_discard_pending_operations()` - Discard incomplete operations
- `_create_pre_import_backup()` - Create backup before import

#### Automatic Corruption Recovery

**Purpose:** When a user attempts to open a corrupted database, automatically detect and offer to restore from the most recent valid backup.

**Corruption Detection:**
Corruption is detected when `_diagnose_database()` returns errors containing:
- "file is not a database"
- "disk i/o error"
- "database disk image is malformed"
- "database or disk is full"
- "unable to open database"

**Recovery Flow:**
1. User attempts to open database (via list selection or browse)
2. `_diagnose_database()` detects corruption error
3. `_find_filesystem_backups()` scans `db_snapshots/` directory for backup files
4. `_validate_backup()` verifies each backup until a valid one is found
5. User shown confirmation dialog with backup details (date, photo count, size)
6. On confirmation:
   - Corrupted file renamed with `.corrupted_TIMESTAMP` suffix
   - Backup copied to original location
   - WAL/SHM files cleaned up
7. Success dialog shows what was recovered and potential data loss

**Key Methods (DatabaseSelectorDialog class):**
- `_find_filesystem_backups(db_path)` - Scan filesystem for backup files (since corrupted DB can't be queried)
- `_validate_backup(backup_path)` - Verify backup integrity and get photo count
- `_attempt_corruption_recovery(db_path, error_message)` - Orchestrate the recovery process

**Filesystem Backup Discovery:**
When database is corrupted, the `QuickBackups` table cannot be queried. Instead, backups are found by:
1. Locating `db_snapshots/` directory next to database
2. Scanning for files matching pattern: `db_snapshot_YYYYMMDD_HHMMSS_<reason>_<uuid8>.db`
3. Parsing timestamp and reason from filename
4. Validating each with `PRAGMA integrity_check`

**User Notification:**
The recovery dialog shows:
- Backup creation date/time
- Backup reason (e.g., "pre import")
- Photo count in backup
- Backup file size

After successful recovery:
- Photos recovered count
- Warning about data loss (files imported after backup)
- Location of preserved corrupted file

**Integration Points:**
- `open_database()` - Re-validates before opening, offers recovery on corruption
- `on_browse_clicked()` - Detects corruption during browse, offers recovery

#### Orphaned File Recovery (Archive Scan)

**Purpose:** After restoring from backup, scan the archive to find files that were imported after the backup was created but are not in the restored database.

**When Offered:**
After successful backup restoration, user is prompted to scan the archive for orphaned files.

**How It Works:**
1. User restores database from backup
2. System offers to scan archive for orphaned files
3. `ArchiveRecoveryWorker` scans archive directory for all media files
4. Each file is hashed and checked against database
5. Files not in database are "orphaned" - imported after backup
6. Orphaned files are added to database with recovery metadata

**Recovery Metadata:**
Recovered files are marked in the database with:
- `source_path` = `RECOVERED:<original_archive_path>`
- `revision_reason` = `recovered_from_archive`
- `revision_timestamp` = recovery timestamp

**Audit Trail:**
- Creates session with `operation_mode='archive_recovery'`
- Logs each file with `operation='archive_recovery'`
- Viewable in Import History under "Archive Recovery" filter

**Worker (`ui/archive_recovery_worker.py`):**
```python
class ArchiveRecoveryWorker(QThread):
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)               # status message
    file_recovered = Signal(dict)             # per-file notification
    completed = Signal(dict)                  # final results
    error_occurred = Signal(str)              # error message
```

**Key Methods (ArchiveRecoveryWorker):**
- `_get_known_hashes()` - Get all file hashes from database
- `_scan_archive()` - Recursively find all media files
- `_recover_file(file_info)` - Add orphaned file to database

**Results Dictionary:**
```python
{
    'cancelled': bool,
    'total_scanned': int,    # Files scanned in archive
    'orphaned_found': int,   # Files not in database
    'recovered': int,        # Successfully added to database
    'failed': int            # Failed to add
}
```

**UI Integration:**
- Dialog shows progress during scan
- Final results show files recovered
- Import History "Archive Recovery" filter shows all recovered files

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

### Bulk Delete Matching Files

Allows users to delete archive files that match files in a reference folder. Useful for removing files that exist in both the archive and an external source (e.g., synced to another device, already backed up elsewhere).

**Two-phase operation:**
1. **Scan phase**: Hash files in reference folder, match against archive database
2. **Delete phase**: Perform soft-delete on confirmed matches (move to Delete Vault)

**Worker (`ui/bulk_delete_worker.py`):**
```python
class BulkDeleteWorker(QThread):
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)              # status message
    scan_completed = Signal(dict)            # scan results for preview
    delete_completed = Signal(dict)          # final deletion results
    error_occurred = Signal(str)             # error message
```

**Preview dialog (`ui/bulk_delete_preview_dialog.py`):**
- Shows matched files (to be deleted) in first tab
- Shows not-found files (not in archive) in second tab
- Displays summary stats (matches, not found, total size)
- Requires confirmation before proceeding with deletion

**UI location:** Archive Maintenance tab → "Bulk Delete Matching Files" group box

**Prerequisites checked at runtime:**
- Database loaded
- Reference folder selected and exists
- Delete Vault configured (required)
- Archive location configured

**Deletion process (follows existing `ui/delete_worker.py` pattern):**
1. Validate file is in archive (not source - source protection)
2. Calculate vault path preserving relative structure
3. Copy file to Delete Vault with `shutil.copy2()`
4. Verify copy (exists + size matches)
5. Delete from archive
6. `mark_file_as_deleted()` - create DeletedFiles record
7. `sync_deletion_to_albums()` - remove from albums with sync_deletions=1
8. Remove from UnreliableDates table
9. Clean up empty directories
10. Log to audit trail

**Audit logging:**
- Session: `operation_mode='bulk_delete'`
- Operations: `'bulk_delete_matched'` (success/failed), `'bulk_delete_not_found'` (skipped)
- Import History filter: "Bulk Delete Operations"

**Undo capability:**
Files are soft-deleted to Delete Vault and can be restored via:
1. Archive Maintenance tab → "View Vault Contents" button
2. Find the deleted files in the DeletedFilesDialog
3. Select files and click "Restore Selected"

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

### Relative Path Storage (Schema v6)

Schema v6 stores relative paths alongside absolute paths for archive portability. This enables databases to work when archives are moved or accessed from different machines.

**New columns in UniquePhotos:**
- `relative_path`: Path relative to archive base (e.g., `2024/01/15/photo.jpg`)
- `storage_type`: Which base the path is relative to: `'archive'`, `'video_archive'`, or `'prior_revision'`

**PathResolver class (`path_resolver.py`):**
```python
from path_resolver import PathResolver
from database_metadata import DatabaseMetadata

db_metadata = DatabaseMetadata(database_path)
resolver = PathResolver(db_metadata)

# Convert relative to absolute
abs_path = resolver.resolve('2024/01/15/photo.jpg', 'archive')

# Convert absolute to relative
rel_path, storage_type = resolver.make_relative('/mnt/photos/2024/01/15/photo.jpg')
```

**Storage type detection priority:**
1. `prior_revision` (check first - may be subdirectory of archive)
2. `video_archive`
3. `archive`
4. `unknown` (fallback if no base matches)

**Migration for existing databases:**
```python
from database_metadata import DatabaseMetadata

db = DatabaseMetadata(database_path)
if db.needs_relative_path_migration():
    success, message = db.run_relative_path_migration()
```

Or via command line:
```bash
python -m migrations.schema_v6_relative_paths /path/to/PhotoDB.db --dry-run
python -m migrations.schema_v6_relative_paths /path/to/PhotoDB.db
```

### Date Extraction System

The system reads all available date metadata and uses an intelligent algorithm to select the most accurate original creation date.

#### EXIF IFD Access (PIL 10.x Fix)

**Important**: In PIL 10.x, `getexif()` only returns the base IFD. DateTimeOriginal and other EXIF-specific tags are in the EXIF sub-IFD, which must be accessed via `get_ifd(IFD.Exif)`:

```python
exif = img.getexif()           # Base IFD only (contains DateTime)
exif_ifd = exif.get_ifd(IFD.Exif)  # EXIF IFD (contains DateTimeOriginal)
gps_ifd = exif.get_ifd(IFD.GPSInfo)  # GPS IFD (contains GPSDateStamp)
```

#### Date Fields Read

| IFD | Tag ID | Field Name | Description |
|-----|--------|------------|-------------|
| Base (IFD0) | 306 | DateTime | File modification time |
| EXIF | 36867 | DateTimeOriginal | When photo was taken (shutter click) |
| EXIF | 36868 | DateTimeDigitized | When image was digitized |
| EXIF | 50971 | PreviewDateTime | When preview was generated |
| GPS | 29 | GPSDateStamp | GPS date (UTC, format: YYYY:MM:DD) |
| GPS | 7 | GPSTimeStamp | GPS time (UTC, tuple of H, M, S) |

#### Image Date Priority Algorithm

1. **DateTimeOriginal** - If present and valid, always use (most authoritative)
2. **Earliest Valid Date** - If no DateTimeOriginal, use the earliest among:
   - DateTimeDigitized
   - GPSDateTime (combined GPSDateStamp + GPSTimeStamp)
   - DateTime
   - PreviewDateTime

   *Rationale*: A file can only be modified AFTER creation, so the earliest date is most likely the original.

3. **IPTC Date Created** - Fallback for images without EXIF (tag 2:55)
4. **OS Metadata** - File creation/modification time (least reliable)
5. **Year 1000 Fallback** - Indicates complete failure

#### Video Date Priority

1. **ffprobe** - `creation_time` tag from format metadata
2. **mutagen** - `©day` tag for MP4/MOV files
3. **QuickTime atoms** - `mvhd` atom creation_time (handles 1904 epoch)
4. **OS Metadata** - File timestamps
5. **Year 1000 Fallback**

#### Date Validation

Dates are validated before use:
- Must be parseable (format: `YYYY:MM:DD HH:MM:SS`)
- Year must be 1990-current+1 (reasonable range for digital photos)
- Not Unix epoch (1970-01-01 00:00:00)
- Not null date (0000:00:00 00:00:00)

#### Unreliable Date Flagging

Dates flagged as unreliable when:
- No EXIF/video metadata found (only OS date available)
- Year equals 1000 (fallback date)
- Year < 1990 (before consumer digital cameras)
- Year > current year + 1 (future date)
- Unix epoch date (1970-01-01)
- File is in a user-specified unreliable path

#### Key Helper Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `_validate_exif_date()` | `DuplicateFileDetection.py` | Validates/parses EXIF date strings |
| `_read_all_exif_dates()` | `DuplicateFileDetection.py` | Reads dates from all IFDs (base, EXIF, GPS) |
| `_select_best_exif_date()` | `DuplicateFileDetection.py` | Implements priority + earliest-date algorithm |
| `_try_iptc_date()` | `DuplicateFileDetection.py` | IPTC date extraction fallback |
| `_try_video_date()` | `DuplicateFileDetection.py` | Video metadata extraction (ffprobe, mutagen, QuickTime) |
| `get_creation_date()` | `DuplicateFileDetection.py` | Main entry point for date extraction |

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

### Source Directory Path Validation

The Import Settings tab validates source directory paths and displays status icons (✓ green checkmark for valid, ⚠ red triangle for invalid). Enhanced diagnostics provide detailed tooltips explaining validation failures.

**Validation Checks (`_validate_path()`):**
1. `os.path.exists(path)` - Path must exist
2. `os.path.isdir(path)` - Must be a directory, not a file
3. `os.access(path, os.R_OK)` - Must have read permission

**Diagnostic Helper Methods:**

| Method | Purpose |
|--------|---------|
| `_diagnose_missing_path()` | Identifies where path breaks, detects mount types, suggests fixes |
| `_diagnose_permission_error()` | Explains permission issues with mount-specific guidance |
| `_diagnose_os_error()` | Handles OS-level errors (stale NFS, timeouts, network unreachable) |

**Network Mount Detection:**

The validation system recognizes and provides specific guidance for:
- **NFS mounts**: Paths containing `-nfs` or `/nfs/`
- **SMB/CIFS shares**: Paths containing `-smb`, `-cifs`
- **GVFS paths**: Paths starting with `/run/user/*/gvfs/`
- **Generic mounts**: Paths under `/mnt/` or `/media/`

**Path Break Detection:**

When a path doesn't exist, the system identifies exactly where it breaks:
```
Path does not exist: /data/NAS-nfs/Photos/Album
Path breaks at: /data/NAS-nfs/Photos
Last valid path: /data/NAS-nfs
```

**OS Error Handling:**

| Error | Status | Guidance |
|-------|--------|----------|
| `ESTALE` | Stale Mount | NFS handle stale, remount needed |
| `ETIMEDOUT` | Timeout | Network share not responding |
| `EHOSTUNREACH` | Unreachable | Network connectivity issue |
| `EACCES` | Permission Denied | Mount options or server permissions |

**Automount Considerations:**

For systems using `x-systemd.automount`, paths may not be accessible until triggered:
- Mount point directory exists but subdirectories don't until accessed
- Browsing to the folder in Files triggers the automount
- Click "Refresh Status" button after mounting to re-validate

**Debug Logging:**

Validation logs at DEBUG level for troubleshooting:
```
Validating path: '/data/NAS-nfs/Photos'
  os.path.exists: True
  os.path.isdir: True
  os.access(R_OK): True
  Result: Available - path is valid
```

**UI Interaction:**
- Hover over ⚠ icon to see detailed diagnostic tooltip
- Click "Refresh Status" to re-validate all source directories
- Tooltips include actionable fix suggestions

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
