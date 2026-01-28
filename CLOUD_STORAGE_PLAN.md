# Cloud Storage Integration Plan

## Executive Summary

This document outlines the implementation plan for adding cloud storage support to PyPhotoOrganizer. The goal is to allow users to configure any of their vaults (main archive, video archive, prior revision archive, delete vault) to use cloud storage instead of or in addition to local storage.

**Key Finding:** The existing architecture is well-positioned for cloud integration:
- Schema v6 already stores **relative paths** (portable across storage backends)
- Multiple vault types already supported (archive, video_archive, prior_revision, delete_vault)
- PendingOperations table provides crash recovery pattern (perfect for cloud)
- PathResolver abstraction exists for path management

**Primary Gap:** File operations use hardcoded `shutil.*` calls throughout `main.py` and other modules.

---

## Supported Cloud Providers (Initial)

| Provider | Use Case | Python SDK |
|----------|----------|------------|
| **Amazon S3** | Primary cloud storage, glacier for archives | `boto3` |
| **Azure Blob Storage** | Enterprise/Microsoft ecosystem | `azure-storage-blob` |
| **Google Cloud Storage** | Google ecosystem integration | `google-cloud-storage` |
| **Backblaze B2** | Cost-effective, S3-compatible | `b2sdk` or S3 API |

**Phase 1:** Amazon S3 (most common, well-documented)
**Phase 2:** Azure Blob Storage, Google Cloud Storage
**Phase 3:** Backblaze B2, other S3-compatible services

---

## Architecture Design

### 1. Storage Backend Abstraction

Create a new module `storage_backend.py` with a unified interface:

```python
from abc import ABC, abstractmethod
from typing import Optional, BinaryIO, Iterator
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FileInfo:
    """Metadata about a file in storage."""
    path: str
    size: int
    modified_time: datetime
    content_hash: Optional[str] = None  # MD5 or SHA-256

class StorageBackend(ABC):
    """Abstract interface for storage operations."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if file exists."""
        pass

    @abstractmethod
    def get_size(self, path: str) -> int:
        """Get file size in bytes."""
        pass

    @abstractmethod
    def get_file_info(self, path: str) -> Optional[FileInfo]:
        """Get file metadata."""
        pass

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """Read entire file into memory (use for small files only)."""
        pass

    @abstractmethod
    def read_file_stream(self, path: str) -> BinaryIO:
        """Get file as readable stream."""
        pass

    @abstractmethod
    def write_file(self, path: str, data: bytes) -> bool:
        """Write data to file."""
        pass

    @abstractmethod
    def write_file_stream(self, path: str, stream: BinaryIO, size: int) -> bool:
        """Write stream to file with known size."""
        pass

    @abstractmethod
    def copy_from_local(self, local_path: str, remote_path: str) -> bool:
        """Upload local file to storage."""
        pass

    @abstractmethod
    def copy_to_local(self, remote_path: str, local_path: str) -> bool:
        """Download file to local filesystem."""
        pass

    @abstractmethod
    def copy(self, source: str, dest: str) -> bool:
        """Copy file within same storage backend."""
        pass

    @abstractmethod
    def move(self, source: str, dest: str) -> bool:
        """Move file within same storage backend."""
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete file."""
        pass

    @abstractmethod
    def makedirs(self, path: str) -> bool:
        """Create directory structure (no-op for object storage)."""
        pass

    @abstractmethod
    def list_files(self, prefix: str) -> Iterator[FileInfo]:
        """List files with given prefix."""
        pass

    @abstractmethod
    def compute_hash(self, path: str, algorithm: str = 'sha256') -> str:
        """Compute hash of file contents."""
        pass
```

### 2. Backend Implementations

#### LocalStorageBackend
```python
class LocalStorageBackend(StorageBackend):
    """Local filesystem storage."""

    def __init__(self, base_path: str):
        self.base_path = base_path

    def _full_path(self, path: str) -> str:
        return os.path.join(self.base_path, path)

    def exists(self, path: str) -> bool:
        return os.path.exists(self._full_path(path))

    def copy_from_local(self, local_path: str, remote_path: str) -> bool:
        dest = self._full_path(remote_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(local_path, dest)
        return True

    # ... etc
```

#### S3StorageBackend
```python
class S3StorageBackend(StorageBackend):
    """Amazon S3 storage backend."""

    def __init__(self, bucket: str, prefix: str = '',
                 region: str = 'us-east-1',
                 credentials_profile: str = None):
        self.bucket = bucket
        self.prefix = prefix.strip('/')
        self.region = region

        import boto3
        session = boto3.Session(profile_name=credentials_profile)
        self.s3 = session.client('s3', region_name=region)

    def _full_key(self, path: str) -> str:
        if self.prefix:
            return f"{self.prefix}/{path}"
        return path

    def exists(self, path: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=self._full_key(path))
            return True
        except self.s3.exceptions.ClientError:
            return False

    def copy_from_local(self, local_path: str, remote_path: str) -> bool:
        key = self._full_key(remote_path)
        self.s3.upload_file(local_path, self.bucket, key)
        return True

    def compute_hash(self, path: str, algorithm: str = 'sha256') -> str:
        # Download and hash, or use S3's ETag (MD5) for small files
        # For large files, use multipart upload checksums
        ...

    # ... etc
```

### 3. Storage Provider Registry

```python
class StorageProviderRegistry:
    """Factory for creating storage backends."""

    _providers = {
        'local': LocalStorageBackend,
        's3': S3StorageBackend,
        'azure': AzureBlobBackend,
        'gcs': GoogleCloudBackend,
    }

    @classmethod
    def create(cls, config: dict) -> StorageBackend:
        """Create storage backend from configuration."""
        storage_type = config.get('type', 'local')

        if storage_type == 'local':
            return LocalStorageBackend(config['path'])

        elif storage_type == 's3':
            return S3StorageBackend(
                bucket=config['bucket'],
                prefix=config.get('prefix', ''),
                region=config.get('region', 'us-east-1'),
                credentials_profile=config.get('credentials_profile')
            )

        elif storage_type == 'azure':
            return AzureBlobBackend(
                container=config['container'],
                connection_string=config.get('connection_string'),
                account_name=config.get('account_name'),
                account_key=config.get('account_key')
            )

        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
```

---

## Configuration Schema

### Updated settings.json Structure

```json
{
    "source_directory": ["D:\\Photos", "/mnt/camera"],

    "storage": {
        "archive": {
            "type": "local",
            "path": "W:\\PhotoArchive"
        },
        "video_archive": {
            "type": "s3",
            "bucket": "my-photo-archive",
            "prefix": "videos",
            "region": "us-west-2",
            "credentials_profile": "photo-organizer"
        },
        "prior_revision": {
            "type": "local",
            "path": "W:\\PriorRevisions"
        },
        "delete_vault": {
            "type": "s3",
            "bucket": "my-photo-archive",
            "prefix": "deleted",
            "region": "us-west-2",
            "storage_class": "GLACIER_IR"
        }
    },

    "cloud_defaults": {
        "upload_threads": 4,
        "chunk_size_mb": 8,
        "retry_attempts": 3,
        "retry_delay_seconds": 5
    },

    "database_path": "PhotoDB.db",
    "batch_size": 100,
    "copy_files": true
}
```

### Backward Compatibility

For existing installations with simple `destination_directory`:

```python
def migrate_config(config: dict) -> dict:
    """Migrate old config format to new storage format."""
    if 'storage' not in config and 'destination_directory' in config:
        config['storage'] = {
            'archive': {
                'type': 'local',
                'path': config['destination_directory']
            }
        }
        # Keep destination_directory for backward compat
    return config
```

---

## Database Schema Updates

### Schema v8: Cloud Storage Support

```sql
-- Update storage_type to support cloud identifiers
-- Existing values: 'archive', 'video_archive', 'prior_revision', 'delete_vault'
-- These remain the same - they identify WHICH vault, not WHERE it is

-- New table to track cloud upload status
CREATE TABLE IF NOT EXISTS CloudSyncStatus (
    file_hash TEXT PRIMARY KEY,
    storage_location TEXT NOT NULL,    -- 'archive', 'video_archive', etc.
    cloud_provider TEXT,               -- 's3', 'azure', 'gcs', NULL for local
    cloud_path TEXT,                   -- Full cloud path (bucket/key)
    upload_status TEXT DEFAULT 'pending',  -- pending, uploading, completed, failed
    upload_started TEXT,
    upload_completed TEXT,
    cloud_etag TEXT,                   -- Cloud provider's integrity tag
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
);

-- Index for finding files that need sync
CREATE INDEX IF NOT EXISTS idx_cloud_sync_status
ON CloudSyncStatus(upload_status, storage_location);

-- Track hybrid scenarios (file in multiple locations)
CREATE TABLE IF NOT EXISTS FileLocations (
    file_hash TEXT,
    location_type TEXT,           -- 'local', 'cloud'
    storage_backend TEXT,         -- 'archive', 'video_archive', etc.
    path TEXT,                    -- Relative path
    verified_at TEXT,             -- Last verification timestamp
    PRIMARY KEY (file_hash, location_type, storage_backend),
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
);
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Foundation)

**Goal:** Create storage abstraction without changing existing behavior

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Create `StorageBackend` ABC | `storage_backend.py` (new) |
| 1.2 | Implement `LocalStorageBackend` | `storage_backend.py` |
| 1.3 | Create `StorageProviderRegistry` | `storage_backend.py` |
| 1.4 | Update config to support new storage format | `config.py` |
| 1.5 | Add backward compatibility migration | `config.py` |
| 1.6 | Update `PathResolver` to use backends | `path_resolver.py` |
| 1.7 | Unit tests for local backend | `tests/unit/test_storage_backend.py` |

**Deliverable:** System works identically to before, but file operations go through `LocalStorageBackend`.

### Phase 2: S3 Integration

**Goal:** Support Amazon S3 as a storage backend

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Implement `S3StorageBackend` | `storage_backend_s3.py` (new) |
| 2.2 | Add multipart upload for large files | `storage_backend_s3.py` |
| 2.3 | Implement S3 hash verification | `storage_backend_s3.py` |
| 2.4 | Add retry logic with exponential backoff | `storage_backend_s3.py` |
| 2.5 | Create database schema v8 | `database_schema.py` |
| 2.6 | Update `organize_files()` for cloud | `main.py` |
| 2.7 | Add progress tracking for uploads | `main.py`, `worker.py` |
| 2.8 | Integration tests with moto (S3 mock) | `tests/integration/test_s3_backend.py` |

**Dependencies:** `boto3`, `moto` (for testing)

### Phase 3: UI Integration

**Goal:** Allow users to configure cloud storage in the GUI

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Create cloud settings widget | `ui/cloud_settings_widget.py` (new) |
| 3.2 | Add cloud config to Archive Settings tab | `ui/archive_settings_tab.py` |
| 3.3 | Add connection test button | `ui/cloud_settings_widget.py` |
| 3.4 | Show upload progress in Progress tab | `ui/progress_tab.py` |
| 3.5 | Add cloud sync status to Import History | `ui/import_history_tab.py` |
| 3.6 | Credential secure storage | `credential_manager.py` (new) |

### Phase 4: Hybrid & Sync Features

**Goal:** Support files in both local and cloud storage

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Implement local-to-cloud sync | `cloud_sync.py` (new) |
| 4.2 | Implement cloud-to-local download | `cloud_sync.py` |
| 4.3 | Add "Sync Now" functionality | `ui/archive_settings_tab.py` |
| 4.4 | Background sync worker | `ui/cloud_sync_worker.py` (new) |
| 4.5 | Conflict resolution for edits | `cloud_sync.py` |
| 4.6 | Storage class transitions (e.g., to Glacier) | `storage_backend_s3.py` |

### Phase 5: Additional Providers

**Goal:** Support Azure Blob and Google Cloud Storage

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Implement `AzureBlobBackend` | `storage_backend_azure.py` (new) |
| 5.2 | Implement `GoogleCloudBackend` | `storage_backend_gcs.py` (new) |
| 5.3 | Add provider selection to UI | `ui/cloud_settings_widget.py` |
| 5.4 | Provider-specific credential flows | `credential_manager.py` |

---

## Key Design Decisions

### 1. Hash Verification Strategy

**Challenge:** Cloud providers use MD5 or proprietary checksums, not SHA-256.

**Solution:**
- Store SHA-256 in database (existing behavior)
- After upload, download first 16KB + last 16KB and verify partial hash
- For critical files, do full verification periodically
- Store cloud provider's ETag for quick integrity checks

```python
def verify_cloud_file(backend: StorageBackend, path: str,
                      expected_hash: str, full_verify: bool = False) -> bool:
    """Verify file integrity in cloud storage."""
    if full_verify:
        cloud_hash = backend.compute_hash(path, 'sha256')
        return cloud_hash == expected_hash
    else:
        # Partial verification - download start/end chunks
        file_info = backend.get_file_info(path)
        if file_info.size < PARTIAL_HASH_MIN_SIZE:
            return verify_cloud_file(backend, path, expected_hash, True)

        # Download and verify partial hash
        partial_data = backend.read_range(path, 0, PARTIAL_HASH_BYTES)
        partial_data += backend.read_range(path, -PARTIAL_HASH_BYTES, None)
        return compute_partial_hash(partial_data) == expected_partial_hash
```

### 2. Credential Management

**Challenge:** Storing cloud credentials securely.

**Solution:**
- Never store credentials in `settings.json`
- Use credential providers in order:
  1. Environment variables (`AWS_PROFILE`, `AZURE_STORAGE_CONNECTION_STRING`)
  2. Standard credential files (`~/.aws/credentials`, `~/.azure/credentials`)
  3. System keyring (`keyring` library) for GUI-entered credentials
  4. OAuth flow for Google Cloud

```python
class CredentialManager:
    """Secure credential storage and retrieval."""

    def get_aws_credentials(self, profile: str = None) -> dict:
        """Get AWS credentials from standard locations."""
        # 1. Check environment
        if os.environ.get('AWS_ACCESS_KEY_ID'):
            return {
                'access_key': os.environ['AWS_ACCESS_KEY_ID'],
                'secret_key': os.environ['AWS_SECRET_ACCESS_KEY']
            }

        # 2. Check AWS credentials file
        # boto3 handles this automatically

        # 3. Check system keyring
        import keyring
        access_key = keyring.get_password('PyPhotoOrganizer', f'aws_{profile}_access_key')
        if access_key:
            return {
                'access_key': access_key,
                'secret_key': keyring.get_password('PyPhotoOrganizer', f'aws_{profile}_secret_key')
            }

        return None

    def store_credentials(self, provider: str, profile: str, credentials: dict):
        """Store credentials in system keyring."""
        import keyring
        for key, value in credentials.items():
            keyring.set_password('PyPhotoOrganizer', f'{provider}_{profile}_{key}', value)
```

### 3. Offline Support

**Challenge:** User may be offline or have intermittent connectivity.

**Solution:**
- Queue uploads when offline
- Store files locally first, then sync to cloud
- Track sync status in `CloudSyncStatus` table
- Show "pending sync" indicator in UI

```python
def organize_file_with_cloud(file_path: str, config: Config,
                             storage: StorageBackend) -> dict:
    """Organize file with cloud support."""
    result = {
        'local_path': None,
        'cloud_status': 'pending'
    }

    # Always write to local first (if local storage configured)
    local_backend = config.get_local_backend()
    if local_backend:
        local_path = organize_to_local(file_path, local_backend)
        result['local_path'] = local_path

    # Queue cloud upload
    if isinstance(storage, CloudStorageBackend):
        queue_cloud_upload(file_hash, local_path, storage)
        result['cloud_status'] = 'queued'

    return result
```

### 4. Cost Optimization

**Challenge:** Cloud storage costs money; minimize unnecessary operations.

**Solution:**
- Use storage classes appropriately:
  - `STANDARD` for main archive (frequently accessed)
  - `INTELLIGENT_TIERING` for video archive
  - `GLACIER_INSTANT_RETRIEVAL` for prior revisions
  - `GLACIER_DEEP_ARCHIVE` for delete vault
- Batch small file uploads
- Use lifecycle policies for automatic transitions

```python
S3_STORAGE_CLASS_MAP = {
    'archive': 'INTELLIGENT_TIERING',
    'video_archive': 'INTELLIGENT_TIERING',
    'prior_revision': 'GLACIER_INSTANT_RETRIEVAL',
    'delete_vault': 'GLACIER_DEEP_ARCHIVE'
}
```

---

## Progress Callback Updates

Update worker to show cloud upload progress:

```python
# New signal for cloud operations
cloud_progress = Signal(int, int, str, str)  # uploaded, total, current_file, status

def _organizing_callback(self, organized, total, current_file,
                        bytes_copied, total_bytes, cloud_status=None):
    """Extended callback with cloud status."""
    self.organizing_progress.emit(organized, total, current_file,
                                  bytes_copied, total_bytes)

    if cloud_status:
        self.cloud_progress.emit(
            cloud_status['uploaded'],
            cloud_status['total'],
            cloud_status['current_file'],
            cloud_status['status']  # 'uploading', 'verifying', 'complete'
        )
```

---

## Testing Strategy

### Unit Tests
- `test_storage_backend.py` - Test `StorageBackend` interface with mocks
- `test_local_backend.py` - Test `LocalStorageBackend` with temp directories
- `test_s3_backend.py` - Test `S3StorageBackend` with `moto` mock

### Integration Tests
- Test full workflow: local file → cloud upload → verification
- Test retry logic with simulated failures
- Test offline mode queuing

### Manual Testing Checklist
- [ ] Configure S3 bucket in UI
- [ ] Import photos to cloud archive
- [ ] Verify files appear in S3 console
- [ ] Test download from cloud
- [ ] Test hybrid mode (local + cloud)
- [ ] Test with intermittent connectivity
- [ ] Verify prior revision archive works with cloud
- [ ] Test delete vault with Glacier storage class

---

## Dependencies

### Required Packages

```txt
# Cloud providers
boto3>=1.28.0          # AWS S3
azure-storage-blob>=12.0.0  # Azure (Phase 5)
google-cloud-storage>=2.0.0  # GCS (Phase 5)

# Credential management
keyring>=24.0.0        # System keyring integration

# Testing
moto>=4.0.0           # AWS mocking for tests
```

### Optional Packages (for specific providers)
```txt
b2sdk>=1.22.0         # Backblaze B2
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data loss during upload | Low | Critical | Verify hash after every upload; keep local copy until verified |
| Credential exposure | Medium | High | Use system keyring; never store in config files |
| Cost overruns | Medium | Medium | Show cost estimates; use lifecycle policies |
| Slow uploads blocking UI | High | Medium | Background upload queue; show progress |
| Cloud provider API changes | Low | Medium | Abstract behind StorageBackend; update one implementation |
| Offline data access | Medium | Medium | Local-first with cloud sync; cache recently accessed |

---

## Success Criteria

### Phase 1 Complete When: **COMPLETED**
- [x] All file operations go through `StorageBackend`
- [x] Existing local-only workflow unchanged
- [x] Unit tests pass for `LocalStorageBackend` (50 tests)

**Files created:**
- `storage_backend.py` - Core abstraction with StorageBackend ABC, LocalStorageBackend, StorageProviderRegistry, StorageManager
- `tests/unit/test_storage_backend.py` - Comprehensive unit tests
- Updated `config.py` with storage config support
- Updated `path_resolver.py` with StorageBackendResolver

### Phase 2 Complete When: **COMPLETED**
- [x] User can configure S3 bucket for main archive
- [x] Photos successfully upload to S3 (with multipart for large files)
- [x] Hash verification passes after upload
- [x] Retry logic handles transient failures (exponential backoff)
- [x] Integration tests pass with moto (when installed)

**Files created:**
- `storage_backend_s3.py` - Full S3 implementation with multipart upload, storage class support
- `cloud_sync_manager.py` - Upload queue management with offline support
- `tests/unit/test_storage_backend_s3.py` - S3 unit tests (skips gracefully without boto3/moto)
- Updated `database_schema.py` to v8 with CloudSyncStatus, FileLocations, CloudUploadQueue tables

### Phase 3 Complete When: **COMPLETED**
- [x] Cloud storage configurable in GUI
- [ ] Upload progress visible in Progress tab (partial - basic infrastructure ready)
- [x] Connection test works
- [ ] Credentials stored securely (deferred to Phase 4 - using AWS profiles for now)

**Files created:**
- `ui/cloud_settings_widget.py` - VaultConfigWidget, CloudSettingsWidget with per-vault config
- Updated `ui/archive_settings_tab.py` to integrate cloud settings
- Updated `database_metadata.py` with storage config methods

### Phase 4 Complete When: **COMPLETED**
- [x] Local-to-cloud sync implemented (CloudSync.sync_vault_to_cloud)
- [x] Cloud-to-local download implemented (CloudSync.download_from_cloud)
- [x] Background sync worker (CloudSyncWorker with pause/resume/stop)
- [x] "Sync Now" UI controls in Archive Settings
- [x] Conflict detection (CloudSync.find_conflicts)
- [x] Conflict resolution (CloudSync.resolve_conflict with multiple strategies)
- [x] Storage class transitions (S3StorageBackend.set_storage_class)

**Files created:**
- `cloud_sync.py` - High-level sync orchestration with conflict resolution
- `ui/cloud_sync_worker.py` - Background worker with progress signals, pause/resume support
- `tests/unit/test_cloud_sync.py` - Unit tests for sync module (12 tests)
- Updated `ui/archive_settings_tab.py` with Sync Now button, progress bar, status display

### Full Feature Complete When:
- [x] All vault types support cloud storage
- [x] Hybrid (local + cloud) mode works
- [x] Background sync operational
- [ ] At least 2 cloud providers supported (S3 complete, Azure/GCS pending - Phase 5)
- [ ] Photo Review app can access cloud files (download-on-demand ready, UI integration pending)

---

## Estimated Effort

| Phase | Scope | Complexity |
|-------|-------|------------|
| Phase 1 | Core Infrastructure | Medium |
| Phase 2 | S3 Integration | High |
| Phase 3 | UI Integration | Medium |
| Phase 4 | Hybrid & Sync | High |
| Phase 5 | Additional Providers | Medium |

---

## Open Questions

1. **Local-first vs Cloud-first:** Should we always keep a local copy, or allow cloud-only vaults?
   - Recommendation: Local-first for reliability, with option for cloud-only delete vault

2. **Album cloud support:** Should albums support cloud storage locations?
   - Recommendation: Phase 2 addition - albums often sync to devices that need local access

3. **Photo Review app:** How should it handle cloud files?
   - Recommendation: Download on-demand with local cache; show cloud indicator

4. **Bandwidth throttling:** Should we limit upload bandwidth?
   - Recommendation: Add as config option in Phase 4

---

*Document created: 2026-01-27*
*Last updated: 2026-01-27*
*Phase 1-3 completed: 2026-01-27*
*Phase 4 completed: 2026-01-27*
