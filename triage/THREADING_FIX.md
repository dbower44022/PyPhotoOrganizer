# Critical Qt Threading Fix - Mouse Wheel Crash

## Issue: Random Crashes During Scrolling

The application was crashing silently when using the mouse wheel to scroll through thumbnails. No Python exceptions were logged - the crash occurred at the Qt C++ level.

## Root Cause: QPixmap Threading Violation ⚠️

**CRITICAL Qt Rule**: QPixmap objects must ONLY be created and accessed from the main GUI thread.

**What was wrong:**
The background worker threads (`ThumbnailWorker`) were creating QPixmap objects:

```python
# WRONG - In worker thread (background):
pixmap = self._pil_to_qpixmap(img)  # Creates QPixmap in worker thread!
self.signals.finished.emit(self.file_hash, self.size, pixmap)
```

When these QPixmaps were accessed during scrolling (in the delegate's paint method), Qt would crash because:
1. QPixmap was created in Thread A (worker)
2. QPixmap was accessed in Thread B (main GUI thread during paint)
3. Qt's internal checks detect thread mismatch → **CRASH** (C++ level, no Python traceback)

## The Fix

### 1. Change Signal Signature
**Before:**
```python
finished = Signal(str, int, QPixmap)  # Emits QPixmap from worker thread - WRONG!
```

**After:**
```python
finished = Signal(str, int, str)  # Emits disk path - worker thread safe!
```

### 2. Worker Thread - Save to Disk Only
**Before:**
```python
img.save(str(disk_path), 'JPEG')
pixmap = self._pil_to_qpixmap(img)  # Creates QPixmap in worker thread!
self.signals.finished.emit(self.file_hash, self.size, pixmap)
```

**After:**
```python
img.save(str(disk_path), 'JPEG')
# Just emit the path - no QPixmap creation in worker thread
self.signals.finished.emit(self.file_hash, self.size, str(disk_path))
```

### 3. Main Thread - Load QPixmap from Disk
**Before:**
```python
def _on_thumbnail_generated(self, file_hash: str, size: int, pixmap: QPixmap):
    # Receives QPixmap from worker thread - UNSAFE!
    self._add_to_memory_cache(cache_key, pixmap)
```

**After:**
```python
def _on_thumbnail_generated(self, file_hash: str, size: int, disk_path: str):
    # This runs in MAIN GUI THREAD - safe to create QPixmap here!
    pixmap = QPixmap(disk_path)  # Load from disk in main thread - SAFE!
    self._add_to_memory_cache(cache_key, pixmap)
```

### 4. Video Placeholder - Use PIL Image
**Before:**
```python
def _create_video_placeholder(self) -> QPixmap:
    pixmap = QPixmap(size, size)  # QPixmap in worker thread!
    # ... draw with QPainter ...
    return pixmap
```

**After:**
```python
def _create_video_placeholder(self) -> Image.Image:
    img = Image.new('RGB', (size, size))  # PIL Image - thread safe!
    # ... draw with ImageDraw ...
    img.save(disk_path, 'JPEG')  # Save to disk
    # Emit path, not pixmap
```

## Files Modified

1. **triage/thumbnail_generator.py**
   - Changed signal signature: `finished = Signal(str, int, str)`
   - Updated `run()` method to emit disk paths
   - Rewrote `_create_video_placeholder()` to use PIL instead of QPixmap

2. **triage/thumbnail_cache.py**
   - Updated `_on_thumbnail_generated()` to load QPixmap from disk path in main thread

3. **triage/ui/thumbnail_delegate.py**
   - Added comprehensive error handling to `paint()` method
   - Added QPixmap type checking: `isinstance(thumbnail, QPixmap)`
   - Added painter validation

## Why This Fixes the Crash

**Thread-Safe Data Flow:**
```
Worker Thread (Background):
  1. PIL opens image
  2. PIL creates thumbnail
  3. Save to disk as JPEG ✓ (file I/O is thread-safe)
  4. Emit disk path (string) ✓ (primitives are thread-safe)

Main GUI Thread:
  5. Receive disk path signal
  6. Load QPixmap from disk ✓ (QPixmap created in main thread!)
  7. Cache QPixmap in memory ✓ (main thread access only)
  8. Delegate paints QPixmap ✓ (main thread access only)
```

## Qt Threading Rules Summary

### ✅ SAFE for Worker Threads:
- File I/O (PIL save/load)
- CPU-intensive operations (image processing)
- Database operations (SQLite with WAL mode)
- Emitting signals with primitive types (str, int, float)

### ❌ UNSAFE for Worker Threads:
- Creating QPixmap, QImage, QPainter
- Accessing GUI widgets (QLabel, QListView, etc.)
- Calling methods on QWidget objects
- Emitting signals with Qt GUI objects

## Testing

**Before fix:**
- App crashes randomly during scrolling
- No error messages in log
- Silent termination

**After fix:**
- Smooth scrolling through thousands of images
- No crashes
- QPixmaps safely created in main thread only

## References

- [Qt Documentation: Thread-Support in Qt Modules](https://doc.qt.io/qt-6/threads-modules.html)
- [QPixmap Class Documentation](https://doc.qt.io/qt-6/qpixmap.html): "QPixmap objects cannot be painted or otherwise used in threads other than the GUI thread"
