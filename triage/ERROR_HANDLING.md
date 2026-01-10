# Error Handling and Crash Reporting

## Overview

Comprehensive error handling has been added to catch and report all crashes with detailed error messages and logging.

## What Was Added

### 1. Main Entry Point (`main_triage.py`)

**Global Exception Handler:**
- Catches ALL unhandled exceptions in Qt event loop
- Logs full stack trace to `triage_app.log`
- Displays error message on console
- Prevents silent crashes

**Startup Error Handling:**
- Window creation wrapped in try-catch
- Database loading wrapped in try-catch
- Window display wrapped in try-catch
- Clear error messages at each stage

**Example Output:**
```
================================================================================
FATAL ERROR - Application crashed!
================================================================================
Traceback (most recent call last):
  File "...", line 123, in some_function
    something.crashed()
AttributeError: 'Something' object has no attribute 'crashed'
================================================================================
Check triage_app.log for details
================================================================================
```

### 2. Main Window (`triage_window.py`)

**Protected Signal Handlers:**
- `_on_folder_selected()` - Shows error dialog on folder load failure
- `_on_selection_changed()` - Logs errors without disrupting UI
- `_on_item_activated()` - Logs errors without disrupting UI

**Error Dialog for Critical Errors:**
```python
QMessageBox.critical(
    self,
    "Folder Load Error",
    f"Failed to load folder:\n{folder_path}\n\nError: {e}\n\nCheck triage_app.log for details"
)
```

### 3. Grid Model (`thumbnail_grid_model.py`)

**Protected load_folder():**
- Wraps entire method in try-catch
- Ensures `endResetModel()` is called even on error
- Re-raises exception for caller to handle
- Prevents model corruption on error

### 4. Preview Pane (`preview_pane.py`)

**Protected show_image():**
- Double-wrapped (inner + outer try-catch)
- Gracefully handles missing files
- Shows error in metadata panel instead of crashing
- Logs all errors for debugging

## Error Reporting Levels

### 1. **Silent Logging** (Selection, Activation)
- Events that fire frequently
- Errors logged to file only
- No user dialogs (too disruptive)
- Use for: selection changes, hover events

### 2. **Status Bar Messages** (Minor Errors)
- Non-critical failures
- Shows brief message in status bar
- Use for: thumbnail generation failures

### 3. **Error Dialogs** (Critical Errors)
- Database load failures
- Folder load failures
- Shows modal dialog with details
- Directs user to check log file

### 4. **Fatal Crashes** (Uncaught Exceptions)
- Console output with full stack trace
- Logged to file with context
- Application terminates gracefully
- Clear message directing to log file

## Log File Location

**File:** `triage_app.log` in the PyPhotoOrganizer directory

**What's Logged:**
- Application startup/shutdown
- Database operations
- Folder loading
- Thumbnail generation
- All errors with full stack traces
- User actions (folder selection, marking)

**Example Log Entry:**
```
2026-01-09 00:43:32,502 - triage.ui.triage_window - ERROR - Error loading folder /mnt/AllPhotos/...: no such table: TriageActions
Traceback (most recent call last):
  File "triage/ui/triage_window.py", line 363, in _on_folder_selected
    self.grid_model.load_folder(folder_path, recursive=False)
  File "triage/ui/thumbnail_grid_model.py", line 187, in _load_existing_marks
    marked_hashes = self.triage_db.get_marked_hashes(action_type)
sqlite3.OperationalError: no such table: TriageActions
```

## Debug Mode

Enable verbose logging:

```bash
python triage/main_triage.py --debug
```

**Debug mode logs:**
- All INFO, WARNING, ERROR, CRITICAL messages
- Detailed function entry/exit
- Database queries
- Cache operations
- Performance metrics

## How to Debug Crashes

### Step 1: Check Console Output

Look for the error message banner:
```
================================================================================
FATAL ERROR - Application crashed!
================================================================================
```

Read the stack trace to see where it failed.

### Step 2: Check triage_app.log

```bash
tail -100 triage_app.log
```

Look for ERROR or CRITICAL messages near the end.

### Step 3: Run in Debug Mode

```bash
python triage/main_triage.py --debug
```

Repeat the action that caused the crash. The log will have much more detail.

### Step 4: Check for Common Issues

**Database errors:**
- "no such table" → Run database migration script
- "database is locked" → Close other applications accessing DB
- "database disk image is malformed" → Database corrupted

**File access errors:**
- "Permission denied" → Check file/folder permissions
- "File not found" → Archive location moved or disconnected
- "Too many open files" → Reduce worker threads in config

**Memory errors:**
- "Out of memory" → Reduce `memory_cache_size` in config
- "Cannot allocate memory" → Close other applications

**Qt/GUI errors:**
- "QPixmap: Invalid pixmap" → File is corrupted or wrong format
- "Cannot create QWidget" → Display/graphics driver issue

## Error Recovery

### Automatic Recovery

The application attempts to recover from errors:
- **Thumbnail errors** → Shows placeholder, continues
- **Selection errors** → Logs error, clears selection
- **Preview errors** → Shows error in panel, continues

### Manual Recovery

If the application becomes unstable:
1. **Save your work** → Export marked files
2. **Restart application**
3. **Reload database**
4. **Your marks are saved** → They persist in database

## Reporting Bugs

When reporting crashes, include:
1. **Console output** (the error banner and stack trace)
2. **Last 50 lines of triage_app.log**
3. **Steps to reproduce** the crash
4. **System info** (OS, Python version, database size)

**Example:**
```
Bug: Application crashes when loading folder with 100k images

Console output:
================================================================================
FATAL ERROR - Application crashed!
================================================================================
RuntimeError: maximum recursion depth exceeded
...

Log file (last 50 lines):
2026-01-09 00:43:32 - ERROR - Stack overflow in load_folder
...

Steps to reproduce:
1. Open database with 500k images
2. Click on folder /archive/2025/
3. Application crashes immediately

System:
- Ubuntu 24.04
- Python 3.12
- Database: 2.5GB with 500k images
```

## Known Limitations

### Unrecoverable Errors

Some errors will always crash:
- **Out of memory** → Close app, reduce cache size
- **Database corruption** → Restore from backup
- **Qt display errors** → Graphics driver issue
- **Python segfault** → C library crash (rare)

### Error Suppression

Some errors are intentionally suppressed:
- **Video thumbnail failures** → Shows placeholder
- **Missing thumbnails** → Shows "Loading..."
- **Invalid image files** → Shows error icon

## Best Practices

### For Users

1. **Check logs first** before reporting
2. **Export marks regularly** (in case of crash)
3. **Use debug mode** to diagnose issues
4. **Keep backups** of your database

### For Developers

1. **Always log errors** with `exc_info=True`
2. **Catch specific exceptions** when possible
3. **Show user-friendly messages**
4. **Clean up resources** in finally blocks
5. **Test error paths** as much as success paths

## Error Handling Checklist

When adding new features, ensure:
- [ ] All signal handlers wrapped in try-catch
- [ ] Database operations use context managers
- [ ] File operations check existence first
- [ ] Errors logged with full stack trace
- [ ] User shown helpful error message
- [ ] Resources cleaned up in finally block
- [ ] Model reset called even on error
- [ ] Application can recover and continue

---

**With comprehensive error handling, crashes should now:**
1. ✅ Be logged to file with full details
2. ✅ Show clear error messages
3. ✅ Direct user to check log file
4. ✅ Prevent silent failures
5. ✅ Allow debugging and diagnosis

**No more mysterious terminations!** 🎉
