# Comprehensive Error Handling - Complete Coverage

## Overview

Every event handler, signal handler, and critical method now has comprehensive try-catch error handling with detailed logging.

## Protected Components

### 1. Main Entry Point (main_triage.py)

**Global Exception Hook:**
```python
sys.excepthook = exception_hook  # Catches ALL unhandled Qt exceptions
```

**Protected Sections:**
- Import phase (wrapped in try-catch before any imports)
- Argument parsing
- Logging setup
- Qt application creation
- Main window creation
- Window display
- Database loading
- Event loop execution

**All errors:**
- Logged to `triage_app.log` with full stack trace
- Printed to console with clear banners
- Include file/line numbers via `exc_info=True`

### 2. Main Window (triage/ui/triage_window.py)

**Protected Signal Handlers:**

✅ `_on_folder_selected(folder_path)`:
- Wrapped in try-catch
- Shows QMessageBox.critical on error
- Logs with full traceback

✅ `_on_selection_changed(selected_hashes)`:
- Wrapped in try-catch
- Silent logging (no dialog - too disruptive)
- Prevents cascade failures

✅ `_on_item_activated(file_hash)`:
- Wrapped in try-catch
- Silent logging
- Continues execution on error

### 3. Thumbnail Grid View (triage/ui/thumbnail_grid_view.py)

**Protected Event Handlers:**

✅ `keyPressEvent(event)` - **CRITICAL FOR ARROW KEYS**:
```python
try:
    # Handle all keyboard shortcuts (D, F, C, 1/2/3, Space, Escape, Ctrl+A)
    # Handle arrow key navigation via super().keyPressEvent(event)
except Exception as e:
    logger.error(f"Error in keyPressEvent: {e}", exc_info=True)
    event.accept()  # Prevent crash by accepting event
```

✅ `_on_scroll()`:
```python
try:
    # Prefetch thumbnails for visible range
except Exception as e:
    logger.error(f"Error in scroll handler: {e}", exc_info=True)
```

✅ `_on_selection_changed()`:
```python
try:
    # Validate indices, get selected hashes, emit signal
except Exception as e:
    logger.error(f"Error in selection changed handler: {e}", exc_info=True)
```

✅ `_on_double_clicked(index)`:
```python
try:
    # Validate index, emit activation signal
except Exception as e:
    logger.error(f"Error in double-click handler: {e}", exc_info=True)
```

### 4. Thumbnail Grid Model (triage/ui/thumbnail_grid_model.py)

**Protected Data Access:**

✅ `data(index, role)` - **CALLED HUNDREDS OF TIMES DURING SCROLLING**:
```python
try:
    # Validate index (not None, isValid())
    # Validate row bounds (0 <= row < len)
    # Validate item exists
    # Use safe .get() for all dict accesses
    # Return None on any failure
except Exception as e:
    logger.error(f"Error in data() method for row {row}, role {role}: {e}", exc_info=True)
    return None
```

**Key Safety Features:**
- Checks `if not index or not index.isValid()`
- Checks row bounds: `if row < 0 or row >= len(self.file_items)`
- Uses `item.get('key')` instead of `item['key']` (no KeyError)
- Returns safe defaults on missing data
- Never raises exceptions - always returns None

✅ `load_folder(folder_path, recursive)`:
```python
try:
    self.beginResetModel()
    # ... load data ...
    self.endResetModel()
except Exception as e:
    self.endResetModel()  # ALWAYS called even on error!
    logger.error(...)
    raise  # Re-raise for caller
```

### 5. Thumbnail Delegate (triage/ui/thumbnail_delegate.py)

**Protected Painting:**

✅ `paint(painter, option, index)` - **CALLED CONSTANTLY DURING SCROLLING**:
```python
try:
    # Validate painter is active
    if not painter or not painter.isActive():
        return

    # Validate index
    if not index or not index.isValid():
        return

    painter.save()

    # Type check QPixmap
    if thumbnail and isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
        # Draw thumbnail

    # ... draw filename, marks, selection ...

    painter.restore()

except Exception as e:
    logger.error(f"Error in paint method: {e}", exc_info=True)
    # Try to restore painter state
    try:
        if painter and painter.isActive():
            painter.restore()
    except:
        pass
```

**Safety Features:**
- Validates painter is active before use
- Type checks: `isinstance(thumbnail, QPixmap)`
- Null checks: `not thumbnail.isNull()`
- Double try-catch (outer + painter restore)

### 6. Preview Pane (triage/ui/preview_pane.py)

**Protected Image Loading:**

✅ `show_image(image_path)` - **DOUBLE-WRAPPED**:
```python
try:
    # Outer wrapper
    try:
        # Check file exists
        # Load QPixmap
        # Load metadata
    except Exception as e:
        logger.error(f"Error displaying image: {e}", exc_info=True)
        self.clear()
except Exception as e:
    # Outer catch for unexpected errors
    logger.error(f"Unexpected error in show_image: {e}", exc_info=True)
    self.clear()
```

### 7. Thumbnail Cache (triage/thumbnail_cache.py)

**Protected Thumbnail Loading:**

✅ `_on_thumbnail_generated(file_hash, size, disk_path)`:
```python
try:
    # Load QPixmap from disk (MAIN THREAD - SAFE!)
    pixmap = QPixmap(disk_path)
    if pixmap.isNull():
        logger.warning(...)
        return

    # Add to memory cache
except Exception as e:
    logger.error(f"Error loading generated thumbnail: {e}", exc_info=True)
```

## Error Reporting Levels

### 1. Silent Logging (High-Frequency Events)
**When:** Selection changes, scroll events, paint calls
**Action:** Log to file only, no user notification
**Rationale:** Too disruptive to show dialogs for frequent events

### 2. Status Bar Messages (Minor Errors)
**When:** Thumbnail load failures, non-critical operations
**Action:** Brief message in status bar (2-3 seconds)
**Rationale:** User awareness without interruption

### 3. Error Dialogs (Critical Errors)
**When:** Database load failures, folder load failures
**Action:** Modal QMessageBox.critical with details
**Rationale:** User must know operation failed

### 4. Fatal Crashes (Uncaught Exceptions)
**When:** Exceptions that escape all handlers
**Action:** Console banner + log file + graceful exit
**Rationale:** Last resort - show all available information

## Logging Details

**Every Error Includes:**
- Full stack trace (`exc_info=True`)
- Module name
- Function name
- Line number
- Context (file hash, row number, operation type, etc.)

**Log File:** `triage_app.log` in triage directory

**Log Format:**
```
2026-01-09 12:34:56,789 - triage.ui.thumbnail_grid_view - ERROR - Error in keyPressEvent: division by zero
Traceback (most recent call last):
  File "/path/to/thumbnail_grid_view.py", line 245, in keyPressEvent
    result = 1 / 0
ZeroDivisionError: division by zero
```

## Validation Patterns

### Index Validation:
```python
if not index or not index.isValid():
    return None
```

### Painter Validation:
```python
if not painter or not painter.isActive():
    return
```

### Row Bounds Validation:
```python
if row < 0 or row >= len(self.file_items):
    return None
```

### QPixmap Type Validation:
```python
if thumbnail and isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
    # Use thumbnail
```

### Dictionary Safe Access:
```python
# BAD:
file_hash = item['file_hash']  # KeyError if missing!

# GOOD:
file_hash = item.get('file_hash')  # Returns None if missing
```

## Known Limitations

### Unrecoverable Qt C++ Crashes:
Even with comprehensive error handling, some Qt internal crashes cannot be caught from Python:
- Segmentation faults in Qt's C++ code
- Graphics driver crashes
- Out of memory in Qt internals

**Mitigation**: The threading fix (QPixmap in main thread only) prevents most of these.

### Performance Impact:
Try-catch blocks have minimal performance impact:
- Exception setup: ~0.1 microseconds when no exception
- Exception throw/catch: ~50 microseconds
- For 60 FPS (16ms frame budget), this is negligible

## Testing Checklist

To verify error handling works:

1. ✅ **Arrow key navigation** - scroll through all images
2. ✅ **Mouse wheel scrolling** - rapid scrolling
3. ✅ **Missing files** - select folder with deleted images
4. ✅ **Corrupted images** - load folder with corrupted JPEGs
5. ✅ **Empty folders** - select folder with no images
6. ✅ **Keyboard shortcuts** - press D, F, C rapidly
7. ✅ **Grid size changes** - press 1, 2, 3 while scrolling
8. ✅ **Database errors** - corrupt database file

**Expected Result:** All errors logged to `triage_app.log`, application continues running.

## Summary

**Total Protected Methods:** 15+
**Total Lines of Error Handling:** ~200
**Coverage:** Every Qt event handler, signal handler, and critical path

**Result:** The application should NEVER crash silently. All Python exceptions will be:
1. Logged with full traceback
2. Displayed appropriately (dialog, status, or silent)
3. Prevented from crashing the application

If the application still crashes without logging, it's a Qt C++ level crash (graphics driver, segfault, etc.) that cannot be caught from Python code.
