# CLAUDE_DATABASE.md

Database schema, health monitoring, backup/recovery systems for PyPhotoOrganizer.

**See also:** [CLAUDE.md](CLAUDE.md) for core project guidelines.

## Database Tables

All tables in SQLite database (default: `PhotoDB.db`):

| Table | Purpose |
|-------|---------|
| `DatabaseMetadata` | Archive location, settings, schema version |
| `UniquePhotos` | File hashes, paths, creation dates, revision tracking, content_hash, relative_path, storage_type |
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
| `MetadataUpgradeHistory` | Tracks metadata-based archive file replacements |
| `PendingOperations` | Tracks in-flight copy/move operations for crash recovery |
| `AuditQueue` | Queues failed audit log entries for retry |
| `QuickBackups` | Tracks rolling database snapshots |
| `CloudSyncStatus` | Cloud upload status per file (Schema v8) |
| `FileLocations` | Track file locations across storage backends (Schema v8) |
| `CloudUploadQueue` | Pending cloud uploads with retry support (Schema v8) |

## Schema Version History

### Schema v5
- `FileHashHistory` table deprecated
- All hashes (including revisions) stored in `UniquePhotos` with `file_hash` as primary key
- `revised_photo` column links revisions to parent file

### Schema v6
- Added relative path storage for archive portability
- New `UniquePhotos` columns: `relative_path`, `storage_type` ('archive', 'video_archive', 'prior_revision')
- Related columns: `AlbumPhotos.relative_album_path`, `DeletedFiles.relative_archive_path/relative_vault_path/archive_storage_type`, `UnreliableDates.relative_archive_path`

### Schema v7
- Added metadata quality tracking for intelligent archive upgrades
- New `UniquePhotos` columns: `date_source`, `date_reliable`, `metadata_quality_score`
- New table `MetadataUpgradeHistory`
- New setting `metadata_upgrade_enabled` in `DatabaseMetadata`

### Schema v8
- Added cloud storage support
- New `DatabaseMetadata` columns: `storage_config`, `cloud_sync_enabled`, `cloud_last_sync`, `cloud_defaults`
- New table `CloudSyncStatus`: tracks upload status per file/vault/provider
- New table `FileLocations`: tracks where files exist (local, cloud, both)
- New table `CloudUploadQueue`: offline-capable upload queue with retry logic

## Connection Pattern

All modules use WAL mode for concurrent access:
```python
conn = sqlite3.connect(path, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
```

## Auto-Upgrade Mechanism

`DatabaseMetadata._ensure_metadata_table()` and similar methods automatically add missing columns/tables on first access using `ALTER TABLE ... ADD COLUMN`. No manual migrations needed.

## Table Schemas

### UniquePhotos
```sql
CREATE TABLE UniquePhotos (
    file_hash TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    creation_date TEXT,
    file_size INTEGER,
    content_hash TEXT,
    -- Schema v6
    relative_path TEXT,
    storage_type TEXT,  -- 'archive', 'video_archive', 'prior_revision'
    -- Schema v7
    date_source TEXT,
    date_reliable INTEGER DEFAULT 1,
    metadata_quality_score INTEGER DEFAULT 0,
    -- Revision tracking
    revised_photo TEXT,  -- FK to parent file_hash
    revision_reason TEXT,
    revision_timestamp TEXT
);
```

### PendingOperations (Crash Recovery)
```sql
CREATE TABLE PendingOperations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT UNIQUE NOT NULL,  -- UUID
    operation_type TEXT NOT NULL,        -- 'copy' or 'move'
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL,                -- 'pending', 'copied', 'verified', 'committed', 'failed'
    created_timestamp TEXT NOT NULL,
    error_message TEXT
);
```

**Status Flow:** `pending → copied → verified → (commit) → delete` or `→ failed`

### MetadataUpgradeHistory
```sql
CREATE TABLE MetadataUpgradeHistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upgrade_timestamp TEXT NOT NULL,
    session_id TEXT,
    original_file_hash TEXT NOT NULL,
    incoming_file_hash TEXT NOT NULL,
    original_date_source TEXT,
    original_metadata_score INTEGER,
    incoming_date_source TEXT,
    incoming_metadata_score INTEGER,
    original_date TEXT,
    incoming_date TEXT,
    archive_path TEXT NOT NULL,
    prior_revision_path TEXT NOT NULL,
    date_changed INTEGER DEFAULT 0
);
```

### AuditQueue
```sql
CREATE TABLE AuditQueue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_timestamp TEXT NOT NULL,
    log_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
);
```

### QuickBackups
```sql
CREATE TABLE QuickBackups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_path TEXT NOT NULL,
    backup_reason TEXT NOT NULL,  -- 'pre_import', 'pre_batch_edit', 'auto'
    created_timestamp TEXT NOT NULL,
    database_size_bytes INTEGER,
    is_valid INTEGER DEFAULT 1
);
```

### SourceDirectorySubAlbums
```sql
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

## Database Health System

### Health Check Method

```python
def check_database_health(self) -> Dict[str, Any]:
    """Returns: {healthy, issues, warnings, pending_ops, wal_size_mb, integrity_ok}"""
```

**Checks performed:**
1. `PRAGMA integrity_check` - Database corruption
2. Pending operations count - Crash recovery needed
3. WAL file size - Warns if >50MB
4. Audit queue count - Failed entries awaiting retry

### Startup Health Check Flow

1. Call `check_database_health()`
2. If not healthy: show error dialog
3. If pending operations: offer recovery
4. Process queued audits silently
5. Show warnings if any

## Backup System

### Quick Backups

- **Location:** `<database_directory>/db_snapshots/`
- **Filename:** `db_snapshot_YYYYMMDD_HHMMSS_<reason>_<uuid8>.db`
- **Retention:** Last 5 snapshots kept

**Key Methods (DatabaseMetadata):**
- `create_quick_backup(reason)` - Create snapshot
- `get_quick_backups()` - List available
- `restore_quick_backup(backup_id)` - Restore
- `_cleanup_old_quick_backups(keep_count)` - Maintain rolling window

### Pre-Import Backup

Called automatically before starting import via `_create_pre_import_backup()`.

## Crash Recovery

### Pending Operations

Track multi-step operations (copy → verify → commit) for recovery after crash.

**Key Methods (DatabaseMetadata):**
- `create_pending_operation()` - Record before starting
- `update_pending_status()` - Update progress
- `get_incomplete_operations()` - Find for recovery
- `delete_pending_operation()` - Remove after success
- `cleanup_old_pending_operations(days_old)` - Remove stale

### Recovery Logic

On startup, for each incomplete operation:
- `verified`: Just needed commit - mark recovered
- `copied`: Re-verify hash, remove if corrupt
- `pending`/`failed`: Clean up orphaned target file

### Copy Verification

```python
def verify_copy_integrity(dest_path: str, expected_hash: str, retry_count: int = 1) -> tuple:
    """Returns: (verified: bool, actual_hash: str, error_message: str or None)"""
```

## Corruption Recovery

### Detection

Corruption detected when errors contain:
- "file is not a database"
- "disk i/o error"
- "database disk image is malformed"

### Recovery Flow

1. Detect corruption on open attempt
2. Scan `db_snapshots/` for backup files (can't query corrupted DB)
3. Validate each backup with `PRAGMA integrity_check`
4. Show confirmation with backup details
5. Rename corrupted file with `.corrupted_TIMESTAMP` suffix
6. Copy backup to original location
7. Clean up WAL/SHM files

**Key Methods (DatabaseSelectorDialog):**
- `_find_filesystem_backups(db_path)` - Scan for backups
- `_validate_backup(backup_path)` - Verify integrity
- `_attempt_corruption_recovery(db_path, error_message)` - Orchestrate recovery

## Audit Queue (Retry System)

Failed audit log entries are queued for retry instead of being lost.

**Key Methods (DatabaseMetadata):**
- `queue_failed_audit(log_type, payload, error_message)`
- `get_queued_audits(limit)`
- `delete_from_audit_queue(queue_id)`
- `process_queued_unreliable_dates()`

**Retry policy:** Max 5 attempts, cleanup after 30 days.

## Relative Path System (Schema v6)

Enables archive portability when archives are moved or accessed from different machines.

### PathResolver Class

```python
from path_resolver import PathResolver

resolver = PathResolver(db_metadata)
abs_path = resolver.resolve('2024/01/15/photo.jpg', 'archive')
rel_path, storage_type = resolver.make_relative('/mnt/photos/2024/01/15/photo.jpg')
```

**Storage type priority:** `prior_revision` → `video_archive` → `archive` → `unknown`

### Migration

```python
db = DatabaseMetadata(database_path)
if db.needs_relative_path_migration():
    success, message = db.run_relative_path_migration()
```

Or CLI: `python -m migrations.schema_v6_relative_paths /path/to/PhotoDB.db`

## WAL Management

- `_get_wal_size()` - Get WAL file size in bytes
- `checkpoint_wal(mode)` - Force checkpoint (PASSIVE, FULL, RESTART, TRUNCATE)

## Cloud Storage Tables (Schema v8)

### CloudSyncStatus

Tracks upload status for each file in each cloud storage location.

```sql
CREATE TABLE CloudSyncStatus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    storage_location TEXT NOT NULL,  -- 'archive', 'video_archive', etc.
    cloud_provider TEXT,             -- 's3', 'azure', 'gcs'
    cloud_path TEXT,                 -- Path in cloud storage
    upload_status TEXT DEFAULT 'pending',  -- 'pending', 'uploading', 'completed', 'verified', 'failed'
    upload_started TEXT,
    upload_completed TEXT,
    cloud_etag TEXT,                 -- Provider's ETag for integrity
    cloud_storage_class TEXT,        -- S3 storage class
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    verified_at TEXT,
    UNIQUE (file_hash, storage_location, cloud_provider)
);
```

### FileLocations

Tracks where files physically exist (supports hybrid local+cloud).

```sql
CREATE TABLE FileLocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    location_type TEXT NOT NULL,     -- 'local', 'cloud'
    storage_backend TEXT NOT NULL,   -- 'archive', 'video_archive', 's3', etc.
    relative_path TEXT NOT NULL,
    cloud_provider TEXT,
    cloud_bucket TEXT,
    verified_at TEXT,
    UNIQUE (file_hash, location_type, storage_backend)
);
```

### CloudUploadQueue

Persistent queue for cloud uploads with offline support and retry logic.

```sql
CREATE TABLE CloudUploadQueue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    local_path TEXT NOT NULL,
    target_storage TEXT NOT NULL,    -- 'archive', 'video_archive'
    target_path TEXT NOT NULL,       -- Relative path in cloud
    priority INTEGER DEFAULT 0,      -- Higher = sooner
    queued_at TEXT DEFAULT CURRENT_TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    last_attempt TEXT,
    last_error TEXT,
    status TEXT DEFAULT 'queued'     -- 'queued', 'uploading', 'completed', 'failed'
);
```

### DatabaseMetadata Cloud Columns

```sql
-- Added in Schema v8
storage_config TEXT,           -- JSON: per-vault storage configuration
cloud_sync_enabled INTEGER DEFAULT 0,
cloud_last_sync TEXT,
cloud_defaults TEXT            -- JSON: default cloud settings
```

### Storage Config Format

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
  },
  "delete_vault": {
    "provider": "local",
    "path": "/mnt/deleted"
  }
}
```

### Key Methods (DatabaseMetadata)

- `get_storage_config()` / `set_storage_config()` - Per-vault storage configuration
- `get_cloud_defaults()` / `set_cloud_defaults()` - Default cloud settings
- `get_cloud_sync_enabled()` / `set_cloud_sync_enabled()` - Enable/disable sync
- `get_cloud_last_sync()` / `set_cloud_last_sync()` - Last sync timestamp
- `has_cloud_storage()` - Check if any vault uses cloud storage
