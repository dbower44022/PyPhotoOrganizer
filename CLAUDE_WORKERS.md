# CLAUDE_WORKERS.md

Worker thread patterns and cleanup for PyPhotoOrganizer.

**See also:** [CLAUDE.md](CLAUDE.md) for core project guidelines.

## Standard Worker Pattern

All QThread workers follow this signal pattern:

```python
from PySide6.QtCore import QThread, Signal

class MyWorker(QThread):
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)               # status message
    completed = Signal(dict)                  # results dictionary
    error_occurred = Signal(str)              # error message
```

**Note:** For byte counts >2GB, use `Signal(object)` instead of `Signal(int)` to avoid 32-bit overflow.

## Worker Implementations

| Worker | File | Purpose | Extra Signals |
|--------|------|---------|---------------|
| `ProcessingWorker` | `ui/worker.py` | Main import processing | `scanning_progress`, `processing_progress`, `organizing_progress`, `stage_changed` |
| `ReprocessWorker` | `ui/reprocess_worker.py` | Reprocess/override skip | `file_processed(str, str)` for real-time updates |
| `ContentHashBackfillWorker` | `ui/content_hash_worker.py` | Backfill image content hashes | - |
| `VideoContentHashBackfillWorker` | `ui/video_content_hash_worker.py` | Backfill video content hashes | - |
| `ArchiveChangeScannerWorker` | `ui/archive_change_scanner_worker.py` | Detect external modifications | `file_modified(dict)` |
| `BulkDeleteWorker` | `ui/bulk_delete_worker.py` | Bulk delete matching files | `scan_completed(dict)`, `delete_completed(dict)` |
| `ArchiveRecoveryWorker` | `ui/archive_recovery_worker.py` | Recover orphaned files | `file_recovered(dict)` |

## Dialog Worker Cleanup

**Critical:** Dialogs with QThread workers must implement `closeEvent` to prevent thread destruction errors and database locks.

### Required Pattern

```python
from PySide6.QtGui import QCloseEvent

class MyDialog(QDialog):
    def __init__(self, ...):
        super().__init__(...)
        self.worker = None  # Initialize to None

    def closeEvent(self, event: QCloseEvent):
        """Ensure worker thread is properly stopped."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()  # Request graceful stop
            self.worker.wait()    # Block until finished
        event.accept()
```

### Dialogs with Workers

| Dialog | Worker Variable | File |
|--------|-----------------|------|
| `AddToAlbumDialog` | `self.worker` | `ui/add_to_album_dialog.py` |
| `RotateImageDialog` | `self.rotate_worker` | `ui/rotate_image_dialog.py` |
| `BatchEditDialog` | `self.batch_worker` | `ui/batch_edit_dialog.py` |
| `DeletedFilesDialog` | `self.restore_worker` | `ui/deleted_files_dialog.py` |
| `EditImageDialog` | `self.edit_worker` | `ui/edit_image_dialog.py` |

## Tab/Window Worker Cleanup

Tabs and main windows provide `cleanup_workers()` called from main window `closeEvent`.

| Component | Worker(s) | File |
|-----------|-----------|------|
| `MainWindow` | `self.worker` | `ui/main_window.py` |
| `SystemSettingsTab` | `self._backfill_worker`, `self._video_backfill_worker` | `ui/system_settings_tab.py` |
| `ImportHistoryTab` | `self.reprocess_worker`, `self.override_skip_worker` | `ui/import_history_tab.py` |
| `ArchiveMaintenanceTab` | `self._backup_worker`, `self._verification_worker`, `self._storage_stats_worker`, `self._change_scanner_worker` | `ui/archive_maintenance_tab.py` |
| `PhotoReviewWindow` | `self.delete_worker` | `photo_review/review_window.py` |

Main window calls `_cleanup_tab_workers()` in `closeEvent`.

## Graceful Shutdown Pattern

Workers support cooperative cancellation:

1. User clicks "Stop" → `worker.stop()` sets `_should_stop = True`
2. `should_stop` callable passed to processing functions
3. Processing loops check `should_stop()` at start of each file
4. On stop: commits uncommitted work, returns `was_cancelled=True`
5. UI shows accurate partial results

### Implementation

```python
class ProcessingWorker(QThread):
    def __init__(self, ...):
        self._should_stop = False

    def stop(self):
        """Request graceful stop."""
        self._should_stop = True

    def _check_should_stop(self):
        """Callable passed to processing functions."""
        return self._should_stop
```

Progress callbacks return `True` when stop requested to signal cancellation.

**Resume capability:** Re-running skips already-processed files (detected as duplicates via hash).

## Long-Running Process Recovery

- Database commits every `batch_size` files (default: 100)
- On crash at file #5,432, files #1-5,400 are safely saved
- Re-running auto-resumes from where it left off

## ProcessingWorker Stages

The main import worker emits `stage_changed` signal:

1. "Scanning Directories" - `_scan_directories()`
2. "Processing and Organizing Files" - `_organize_files()`

Progress signals:
- `scanning_progress(dirs_scanned, total_dirs, current_dir)`
- `organizing_progress(organized, total, current_file, bytes_copied, total_bytes)`

## ReprocessWorker Album Support

```python
ReprocessWorker(
    database_path=...,
    file_records=...,
    archive_location=...,
    organization_template=...,
    copy_mode=True,
    audit_manager=...,
    album_manager=album_manager,              # Optional
    source_album_mapping=source_album_mapping # Optional: {source_path: {'album_id': int, 'enable_sub_albums': bool}}
)
```

After successful insert:
1. Finds matching source directory
2. Handles sub-albums if enabled
3. Adds file to album
4. Emits `file_processed` signal
