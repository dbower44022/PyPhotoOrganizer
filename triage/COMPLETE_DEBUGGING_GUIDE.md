# Complete Debugging Guide: Qt Thumbnail Grid Crashes

## Executive Summary

This document chronicles the complete debugging journey to fix persistent crashes in a PySide6/Qt thumbnail grid application. The application would crash whenever folders with uncached thumbnails were selected. Through systematic debugging, two critical root causes were identified and fixed:

1. **Returning None/invalid QPixmap for missing thumbnails** caused Qt internal C++ crashes
2. **Missing signal/slot connections** prevented view updates when thumbnails loaded asynchronously

**Final Solution**:
- Return null QPixmap (`QPixmap()` with no size) for missing thumbnails
- Implement proper signal/slot system for async data updates

**Time to fix**: ~6 hours of iterative debugging
**Result**: Fully stable application with smooth progressive thumbnail loading

---

## Table of Contents

1. [The Problem](#the-problem)
2. [Investigation Timeline](#investigation-timeline)
3. [Root Causes Discovered](#root-causes-discovered)
4. [Failed Attempts](#failed-attempts)
5. [Final Working Solution](#final-working-solution)
6. [Key Lessons Learned](#key-lessons-learned)
7. [Best Practices](#best-practices)
8. [Debugging Techniques](#debugging-techniques)
9. [Qt-Specific Gotchas](#qt-specific-gotchas)

---

## The Problem

### Symptoms

**Application behavior**:
- ✅ Works perfectly with cached thumbnails
- ❌ Crashes immediately when loading folders with uncached thumbnails
- ❌ No Python exceptions thrown (C++ level crashes)
- ❌ No error messages in logs
- ❌ Crashes before delegate.paint() is called

**User experience**:
- Application starts normally
- Selecting first folder (with cached thumbnails) works fine
- Selecting second folder (without cached thumbnails) → immediate crash
- Complete application termination, no recovery possible

### Environment

- **Framework**: PySide6 (Qt 6)
- **Python**: 3.13
- **OS**: Linux
- **Architecture**: QListView with QAbstractListModel and QStyledItemDelegate
- **Use case**: Display 100,000+ photo thumbnails with virtual scrolling

### The Challenge

**Why this was difficult to debug**:

1. **Silent failures**: Qt C++ crashes don't throw Python exceptions
2. **Timing-dependent**: Crashes occurred at different points in execution
3. **Non-deterministic**: Sometimes worked, sometimes crashed
4. **No stack traces**: C++ segfaults don't provide Python call stacks
5. **Complex architecture**: Model/View/Delegate/Cache/Workers interaction

---

## Investigation Timeline

### Phase 1: Initial Debugging (Hour 1)

**Hypothesis**: File validation issues causing thumbnail loading failures

**Approach**: Add defensive file validation
- Validate file exists before opening
- Check file size > 0 bytes
- Verify thumbnail saved successfully
- Add extensive error handling

**Result**: ❌ Still crashed immediately

**Learning**: The problem wasn't in file I/O or thumbnail generation

### Phase 2: Placeholder Investigation (Hour 2)

**Hypothesis**: Creating QPixmap placeholders with text/drawing operations causes crashes

**Approach**: Simplify placeholder creation
- Removed all QPainter.drawText() calls
- Removed fillRect() operations
- Disabled all drawing in delegate when thumbnail not ready

**Result**: ❌ Still crashed

**Learning**: Any drawing operation was suspect, but removing them didn't help

### Phase 3: QPixmap Creation Investigation (Hour 3)

**Hypothesis**: Creating QPixmap objects in memory (not from disk) causes Qt crashes

**Evidence**:
```
Log: Thumbnails load from disk → Works perfectly
Log: Gray box placeholders shown (QPixmap created) → Crash immediately
```

**Approach**: Return None instead of creating placeholder QPixmap

**Result**: ❌ Still crashed

**Learning**: The crash was related to what the model returned, not just placeholder creation

### Phase 4: Null Value Investigation (Hour 4)

**Hypothesis**: Returning Python None for DecorationRole causes Qt internal crashes

**Evidence from logs**:
```
data() ENTRY - returning None
Cache returned None
[CRASH - no delegate paint() logs]
```

**Approach 1**: Return QVariant() (Qt's empty value)

**Result**: ❌ Import error - QVariant doesn't exist in PySide6/Qt6

**Approach 2**: Return null QPixmap (QPixmap() with no size)

**Result**: ✅ **Significant improvement** - worked for 6+ folder changes before crashing

**Learning**: Null QPixmap is Qt's proper way to represent "no image"

### Phase 5: Signal/Slot Investigation (Hour 5)

**Hypothesis**: View never notified when thumbnails finish loading asynchronously

**Evidence**:
```python
# Comment in code:
# Note: Grid view should connect to worker.signals.finished to redraw
# when thumbnail becomes available

# Reality:
# No such connection existed anywhere
```

**Observation**: Application worked initially with null QPixmap but crashed after multiple operations, suggesting state accumulation/inconsistency

**Approach**: Add thumbnail_ready signal to notify model when thumbnails load

**Result**: ✅ **Fully stable** - no crashes, smooth operation

**Learning**: Qt's model/view architecture requires explicit dataChanged signals

---

## Root Causes Discovered

### Root Cause #1: Invalid Return Values for DecorationRole

**The Problem**:

Qt's model/view rendering expects very specific return values for `Qt.DecorationRole`:

| Return Value | Qt's Behavior | Result |
|--------------|---------------|--------|
| Valid QPixmap from disk | Renders image | ✅ Works |
| `None` | Tries to convert to QVariant, fails | ❌ Crashes |
| `QPixmap(1, 1).fill(color)` | Valid pixmap, tries to render | ❌ Crashes |
| Fresh `QPixmap(1, 1)` per item | Valid pixmap, tries to render | ❌ Crashes |
| `QPixmap()` (null, no size) | Recognizes as null, skips rendering | ✅ Works |

**Why this crashes**:

Qt's internal C++ rendering code:
```cpp
// Pseudo-code of what Qt does internally
QVariant variant = model->data(index, Qt::DecorationRole);
if (variant.canConvert<QPixmap>()) {
    QPixmap pixmap = variant.value<QPixmap>();
    if (!pixmap.isNull()) {
        // Draw the pixmap
        painter->drawPixmap(..., pixmap);  // ← Crashes here with artificial pixmaps
    }
}
```

**The issue**: Artificially created QPixmaps (not loaded from image data) don't have proper internal metadata that Qt's rendering expects, causing null pointer dereferences or validation failures in C++ code.

**The solution**: Return a null QPixmap (`QPixmap()` with `isNull() == True`), which Qt recognizes and skips rendering entirely.

### Root Cause #2: Missing Signal/Slot Connections

**The Problem**:

Asynchronous data updates require explicit notification in Qt's model/view architecture:

```
1. User requests data (via view)
2. Model returns "no data yet" (null pixmap)
3. View displays empty space
4. Background worker generates data
5. Data becomes available in cache
6. [MISSING STEP] Model never notifies view
7. View continues showing empty space with stale null pixmap
8. State inconsistency accumulates
9. Eventually crashes
```

**Why this crashes**:

Without `dataChanged` signal:
- View caches the "null pixmap" result
- Model's cache now has valid pixmap
- View and model are out of sync
- Future operations assume consistent state
- Qt internal code accesses stale pointers
- Segmentation fault

**The solution**: Emit `dataChanged` signal when background data becomes available, triggering view to re-request data and repaint.

---

## Failed Attempts

### Attempt 1: Add File Validation

**What we tried**:
```python
# Validate file exists
if not os.path.exists(file_path):
    raise FileNotFoundError(...)

# Validate file size
if os.path.getsize(file_path) == 0:
    raise ValueError(...)

# Verify thumbnail saved
if not os.path.exists(thumbnail_path):
    raise IOError(...)
```

**Why it failed**: The crash wasn't in file I/O, it was in Qt's rendering pipeline

### Attempt 2: Disable All QPainter Drawing

**What we tried**:
```python
# Commented out all drawing operations
# - painter.fillRect()
# - painter.drawText()
# - painter.drawRect()

# Delegate just skips drawing when thumbnail not ready
if thumbnail is None:
    pass  # Draw nothing
```

**Why it failed**: The crash occurred before delegate.paint() was even called

### Attempt 3: Return None When Thumbnail Not Ready

**What we tried**:
```python
# In cache.get_thumbnail()
if thumbnail_not_ready:
    return None  # Let delegate handle it

# In model.data()
if pixmap is None:
    return None  # Tell view "no decoration"
```

**Why it failed**: Python None doesn't convert properly to Qt's null pixmap, causes internal crashes

### Attempt 4: Create Placeholder QPixmap (Shared Instance)

**What we tried**:
```python
# In model.__init__()
self._placeholder = QPixmap(1, 1)
self._placeholder.fill(QColor(80, 80, 100))

# In model.data()
if pixmap is None:
    return self._placeholder  # Same instance for all items
```

**Why it failed**:
- Sharing QPixmap instance across items causes rendering conflicts
- Artificially created QPixmaps crash Qt's rendering anyway

### Attempt 5: Create Fresh Placeholder QPixmap Per Request

**What we tried**:
```python
# In model.data()
if pixmap is None:
    placeholder = QPixmap(1, 1)
    placeholder.fill(QColor(80, 80, 100))
    return placeholder  # Fresh instance each time
```

**Why it failed**: Artificially created QPixmaps (even fresh ones) crash Qt's rendering

### Attempt 6: Return QVariant() (Empty Variant)

**What we tried**:
```python
from PySide6.QtCore import QVariant

if pixmap is None:
    return QVariant()  # Qt's native empty value
```

**Why it failed**: `QVariant` doesn't exist in PySide6/Qt6 (removed in Qt6, Python types used directly)

---

## Final Working Solution

### Solution Part 1: Null QPixmap for Missing Thumbnails

**Implementation**:

```python
class ThumbnailGridModel(QAbstractListModel):
    def __init__(self, thumbnail_cache, db_path, parent=None):
        super().__init__(parent)
        # ... other initialization ...

        # Create a null QPixmap to return for missing thumbnails
        # QPixmap() with no size creates a "null" pixmap (isNull() == True)
        self._null_pixmap = QPixmap()  # No size parameters
        logger.info(f"Null pixmap created: isNull={self._null_pixmap.isNull()}")  # True

    def data(self, index, role):
        if role == Qt.DecorationRole:
            pixmap = self.thumbnail_cache.get_thumbnail(...)

            # Thumbnail not ready - return null pixmap
            if pixmap is None:
                return self._null_pixmap  # isNull() == True

            # Validate pixmap before returning
            if not isinstance(pixmap, QPixmap) or pixmap.isNull():
                return self._null_pixmap

            # Pixmap is valid - return it
            return pixmap
```

**Key points**:
- `QPixmap()` with no parameters creates a "null" pixmap
- `isNull()` returns `True` for null pixmaps
- Qt's rendering code checks `isNull()` and skips drawing
- Different from `QPixmap(1, 1)` which creates a valid 1x1 pixmap
- Null pixmap is Qt's intended way to represent "no image"

### Solution Part 2: thumbnail_ready Signal

**Implementation**:

**Step 1: Make cache a QObject with signal**:
```python
from PySide6.QtCore import QObject, Signal

class ThumbnailCache(QObject):
    # Signal emitted when thumbnail finishes generating
    thumbnail_ready = Signal(str, int)  # file_hash, size

    def __init__(self, db_path, cache_dir, ..., parent=None):
        super().__init__(parent)  # Initialize QObject
        # ... rest of initialization ...
```

**Step 2: Emit signal when thumbnail loads**:
```python
def _on_thumbnail_generated(self, file_hash, size, disk_path):
    # Load pixmap from disk
    pixmap = QPixmap(disk_path)

    # Add to memory cache
    self._add_to_memory_cache(cache_key, pixmap)

    # Emit signal to notify model/view
    self.thumbnail_ready.emit(file_hash, size)
```

**Step 3: Connect signal in model**:
```python
class ThumbnailGridModel(QAbstractListModel):
    def __init__(self, thumbnail_cache, db_path, parent=None):
        super().__init__(parent)
        # ... other initialization ...

        # Connect to cache's thumbnail_ready signal
        self.thumbnail_cache.thumbnail_ready.connect(self._on_thumbnail_ready)
```

**Step 4: Handle signal and update view**:
```python
def _on_thumbnail_ready(self, file_hash, size):
    """Handle thumbnail_ready signal from cache."""
    # Only process if size matches current thumbnail size
    if size != self.thumbnail_size:
        return

    # Find the row for this file hash
    for idx, item in enumerate(self.file_items):
        if item.get('file_hash') == file_hash:
            # Emit dataChanged for this item to trigger repaint
            index = self.index(idx, 0)
            self.dataChanged.emit(index, index, [Qt.DecorationRole])
            break
```

**Key points**:
- Cache inherits from `QObject` to support signals
- Signal emitted when async operation completes
- Model connects to signal in `__init__`
- Model emits `dataChanged` to trigger view refresh
- View automatically calls `model.data()` again and repaints

---

## Key Lessons Learned

### Lesson 1: Qt Doesn't Like Artificial QPixmaps

**What we learned**:
- QPixmaps created with `QPixmap(width, height)` and filled with colors don't work reliably
- Qt expects QPixmaps to come from actual image data (files, resources, etc.)
- Internal metadata populated during image loading is required for rendering

**Correct approach**:
- For "no image", use null QPixmap: `QPixmap()` (no size)
- For actual images, load from disk/resources: `QPixmap(file_path)`
- Never create and fill QPixmaps artificially for rendering

### Lesson 2: Qt Model/View Requires Explicit Signals

**What we learned**:
- Views don't automatically poll models for data changes
- Background/async data updates must emit `dataChanged` signal
- Without signals, views show stale data indefinitely
- State inconsistency from missing signals can cause crashes

**Correct approach**:
- Always emit `dataChanged` after data updates
- For async operations, use signals/slots
- Connect cache/worker signals to model handlers
- Model emits `dataChanged` which triggers view refresh

### Lesson 3: Python None ≠ Qt Null

**What we learned**:
- Returning Python `None` from `data()` doesn't create a proper Qt null value
- Qt6/PySide6 removed `QVariant`, Python types used directly
- But Python `None` doesn't convert cleanly to Qt's internal null pixmap

**Correct approach**:
- For "no decoration", return null QPixmap: `QPixmap()`
- Don't return `None` for `Qt.DecorationRole`
- Null QPixmap has `isNull() == True`, which Qt checks explicitly

### Lesson 4: Qt Crashes Are Silent

**What we learned**:
- Qt C++ crashes don't throw Python exceptions
- Segmentation faults terminate the process immediately
- No stack traces, no error messages
- Makes debugging extremely difficult

**Correct approach**:
- Add extensive logging BEFORE operations (not just after)
- Log entry to functions, not just exits
- Use process of elimination (disable features one by one)
- Test with minimal reproducible examples

### Lesson 5: Virtual Scrolling Requires Careful State Management

**What we learned**:
- Virtual scrolling means items appear/disappear dynamically
- Data can change while items are off-screen
- View might request data for items that are no longer relevant
- Async operations can complete after user navigated away

**Correct approach**:
- Cancel pending operations when switching folders
- Check current state before acting on signals
- Ignore signals for items not in current dataset
- Clear caches appropriately during navigation

---

## Best Practices

### For Qt Model/View Architecture

1. **Always emit dataChanged after updates**:
   ```python
   # After any data modification
   top_left = self.index(first_row, 0)
   bottom_right = self.index(last_row, 0)
   self.dataChanged.emit(top_left, bottom_right, [Qt.DecorationRole])
   ```

2. **Return proper Qt types from data()**:
   - For images: Valid QPixmap or null QPixmap (`QPixmap()`)
   - For text: QString or Python str
   - For numbers: int or float
   - Don't return None for DecorationRole

3. **Use signals for async operations**:
   ```python
   # Bad: Direct update without signal
   self.cache[key] = value  # View won't know

   # Good: Update + signal
   self.cache[key] = value
   self.dataChanged.emit(...)  # View updates
   ```

4. **Inherit from QObject when you need signals**:
   ```python
   class MyCache(QObject):
       data_ready = Signal(str, object)

       def __init__(self, parent=None):
           super().__init__(parent)
   ```

### For Background/Async Operations

1. **Always use signals/slots for thread communication**:
   ```python
   # In worker thread
   self.signals.finished.emit(result)

   # In main thread
   worker.signals.finished.connect(self.on_result)
   ```

2. **Cancel operations when context changes**:
   ```python
   def load_new_folder(self, folder):
       # Cancel pending operations from previous folder
       self.cancel_all_workers()
       # Clear stale cache entries
       self.clear_cache()
       # Load new data
       self.load_folder_data(folder)
   ```

3. **Check validity before acting on signals**:
   ```python
   def on_data_ready(self, item_id):
       # Is this item still relevant?
       if item_id not in self.current_items:
           return  # Ignore stale signal

       # Proceed with update
       self.update_item(item_id)
   ```

### For Debugging Qt Crashes

1. **Add logging BEFORE operations**:
   ```python
   # Bad:
   result = risky_operation()
   logger.info(f"Result: {result}")  # Never reached if crash

   # Good:
   logger.info("About to call risky_operation")
   result = risky_operation()
   logger.info(f"Result: {result}")
   ```

2. **Use process of elimination**:
   - Comment out features one by one
   - Find the minimal code that still crashes
   - Isolate the exact line/operation

3. **Test with simple cases first**:
   - Before testing with 10,000 items, test with 1 item
   - Before testing complex rendering, test with simple text
   - Build complexity gradually

4. **Check Qt documentation for requirements**:
   - Qt has specific expectations for model/view
   - QPixmap has specific creation patterns
   - Signals must be emitted from main thread (or queued)

---

## Debugging Techniques

### Technique 1: Binary Search for Crash Location

**Approach**: Disable half the features, see if crash persists

```python
# Original code (crashes):
def paint(self, painter, option, index):
    draw_background()
    draw_thumbnail()
    draw_text()
    draw_overlays()
    draw_selection()

# Test 1: Disable second half
def paint(self, painter, option, index):
    draw_background()
    draw_thumbnail()
    # draw_text()
    # draw_overlays()
    # draw_selection()
# If still crashes: problem in first half
# If works: problem in second half

# Continue narrowing down...
```

### Technique 2: Aggressive Entry/Exit Logging

**Approach**: Log before and after every operation

```python
def data(self, index, role):
    logger.info(f"data() ENTRY - index.row()={index.row()}, role={role}")

    try:
        logger.info("Checking cache...")
        result = self.cache.get(index.row())
        logger.info(f"Cache returned: {type(result)}")

        logger.info("Returning result")
        return result

    except Exception as e:
        logger.error(f"Exception: {e}", exc_info=True)
        return None

    finally:
        logger.info(f"data() EXIT")
```

If logs show "ENTRY" but no "EXIT", crash happened inside function.
If logs show "Cache returned" but no "Returning", crash happened after getting cache result.

### Technique 3: Test with Minimal Reproducible Example

**Approach**: Create simplest possible test case

```python
# Instead of full application, test just the model:
if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Create model with one item
    model = ThumbnailGridModel(...)
    model.file_items = [
        {'file_hash': 'test123', 'file_path': '/path/to/image.jpg'}
    ]

    # Request data for that item
    index = model.index(0, 0)
    pixmap = model.data(index, Qt.DecorationRole)

    print(f"Got pixmap: {type(pixmap)}, isNull={pixmap.isNull()}")
```

If this crashes, problem is in model.data(), not in view/delegate.

### Technique 4: Compare Working vs. Broken States

**Approach**: Identify exactly what's different

```
Working case (cached thumbnails):
- Cache returns valid QPixmap
- model.data() returns valid QPixmap
- Delegate receives valid QPixmap
- Rendering succeeds

Broken case (uncached thumbnails):
- Cache returns None
- model.data() returns ??? ← INVESTIGATE THIS
- Delegate receives ??? ← AND THIS
- Rendering crashes
```

Focus investigation on the exact point where behavior differs.

---

## Qt-Specific Gotchas

### Gotcha 1: QVariant Removed in Qt6

**What happened in Qt6**:
- Qt5/PySide2 had `QVariant` class for holding any Qt type
- Qt6/PySide6 removed `QVariant`, Python types used directly
- Old code using `QVariant()` won't work in Qt6

**Migration**:
```python
# Qt5/PySide2:
return QVariant()  # Empty variant

# Qt6/PySide6:
return None  # Or appropriate null object (e.g., QPixmap() for images)
```

### Gotcha 2: QPixmap Creation Must Happen in Main Thread

**The rule**: QPixmap and other GUI objects must be created in the main GUI thread

**Wrong**:
```python
# In worker thread
class Worker(QRunnable):
    def run(self):
        pixmap = QPixmap(100, 100)  # ← CRASH or undefined behavior
        pixmap.fill(Qt.red)
        return pixmap
```

**Right**:
```python
# In worker thread - only do file I/O
class Worker(QRunnable):
    def run(self):
        # PIL is thread-safe for I/O
        img = Image.open(file_path)
        img.save(output_path)
        # Emit signal with path, not QPixmap
        self.signals.finished.emit(output_path)

# In main thread - create QPixmap
def on_worker_finished(self, output_path):
    pixmap = QPixmap(output_path)  # ← Safe in main thread
    self.cache[key] = pixmap
```

### Gotcha 3: isNull() vs None

**The difference**:
- Python `None`: Python's null object reference
- QPixmap `isNull()`: Qt's null state for QPixmap

```python
pixmap = QPixmap()  # Creates null QPixmap
print(pixmap is None)  # False - it's an object
print(pixmap.isNull())  # True - but it's null in Qt's sense
```

**Always check both**:
```python
if pixmap is None or pixmap.isNull():
    # Treat as "no pixmap"
    pass
```

### Gotcha 4: Signals Must Match Parameter Types

**Wrong**:
```python
# Signal defined as:
my_signal = Signal(str, int)

# Emitted with wrong types:
self.my_signal.emit(123, "abc")  # ← Will fail or cause undefined behavior
```

**Right**:
```python
# Signal defined as:
my_signal = Signal(str, int)

# Emitted with correct types:
self.my_signal.emit("abc", 123)  # ← Works correctly
```

### Gotcha 5: Model Reset Must Follow Protocol

**Wrong**:
```python
def load_data(self):
    self.data_items.clear()  # ← View doesn't know data changed
    self.data_items.extend(new_items)
```

**Right**:
```python
def load_data(self):
    self.beginResetModel()  # ← Tell view "model is resetting"
    self.data_items.clear()
    self.data_items.extend(new_items)
    self.endResetModel()  # ← Tell view "model reset complete, refresh everything"
```

---

## Prevention Checklist

Use this checklist when implementing Qt model/view architectures:

### Model Implementation

- [ ] Inherit from `QAbstractListModel` or `QAbstractTableModel`
- [ ] Implement required methods: `rowCount()`, `data()`
- [ ] Return appropriate Qt types from `data()` (not Python `None` for images)
- [ ] Emit `dataChanged` after any data modifications
- [ ] Use `beginResetModel()` / `endResetModel()` when replacing all data
- [ ] Validate index before accessing data in `data()` method
- [ ] Return None for invalid/out-of-bounds indices

### Async Operations

- [ ] Create QObjects with signals for background operations
- [ ] Emit signals when async operations complete
- [ ] Connect signals in main thread (model or view)
- [ ] Emit `dataChanged` in signal handlers
- [ ] Cancel pending operations when context changes
- [ ] Check validity before acting on signals (item may no longer exist)

### QPixmap Handling

- [ ] Load QPixmaps from files/resources in main thread
- [ ] Use null QPixmap (`QPixmap()`) for "no image"
- [ ] Don't create artificial QPixmaps by filling colors
- [ ] Check `isNull()` before using QPixmap
- [ ] Don't share QPixmap instances across multiple items

### Debugging Setup

- [ ] Add logging at function entry (before try blocks)
- [ ] Log data types and values, not just "success/failure"
- [ ] Test with minimal examples before full implementation
- [ ] Use binary search to isolate crash locations
- [ ] Check Qt documentation for type requirements

---

## Example: Complete Working Implementation

Here's a complete, minimal example incorporating all lessons learned:

```python
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QListView
import logging

logger = logging.getLogger(__name__)


class ImageCache(QObject):
    """Cache with signal for async loading."""

    # Signal emitted when image finishes loading
    image_ready = Signal(str)  # item_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = {}
        self._null_pixmap = QPixmap()  # Null pixmap for "no image"

    def get(self, item_id, image_path):
        """Get cached image or trigger async load."""
        if item_id in self._cache:
            return self._cache[item_id]

        # Not in cache - start async load (simplified - normally use QThreadPool)
        self._load_async(item_id, image_path)
        return self._null_pixmap  # Return null pixmap while loading

    def _load_async(self, item_id, image_path):
        """Load image asynchronously."""
        # In real implementation, this would be in QRunnable
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self._cache[item_id] = pixmap
            self.image_ready.emit(item_id)  # Signal that image is ready


class ImageListModel(QAbstractListModel):
    """Model with proper signal handling."""

    def __init__(self, image_cache, parent=None):
        super().__init__(parent)
        self.image_cache = image_cache
        self.items = []  # List of {'id': str, 'path': str}

        # Connect to cache signal
        self.image_cache.image_ready.connect(self._on_image_ready)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role):
        if not index.isValid() or index.row() >= len(self.items):
            return None

        item = self.items[index.row()]

        if role == Qt.DisplayRole:
            return item['id']

        elif role == Qt.DecorationRole:
            # Get from cache (returns null pixmap if not ready)
            pixmap = self.image_cache.get(item['id'], item['path'])
            return pixmap  # Never returns None for DecorationRole

        return None

    def load_items(self, items):
        """Load new items with proper reset protocol."""
        self.beginResetModel()
        self.items = items
        self.endResetModel()

    def _on_image_ready(self, item_id):
        """Handle image_ready signal from cache."""
        # Find row for this item
        for row, item in enumerate(self.items):
            if item['id'] == item_id:
                # Emit dataChanged to trigger repaint
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [Qt.DecorationRole])
                break


# Usage
if __name__ == '__main__':
    app = QApplication([])

    cache = ImageCache()
    model = ImageListModel(cache)
    view = QListView()
    view.setModel(model)

    # Load some items
    model.load_items([
        {'id': 'image1', 'path': '/path/to/image1.jpg'},
        {'id': 'image2', 'path': '/path/to/image2.jpg'},
    ])

    view.show()
    app.exec()
```

**This example demonstrates**:
- ✅ Proper QObject inheritance for signals
- ✅ Signal emission after async operations
- ✅ Signal connection in model
- ✅ dataChanged emission in signal handler
- ✅ Null QPixmap for missing images
- ✅ beginResetModel/endResetModel protocol

---

## Conclusion

This debugging journey revealed fundamental patterns and anti-patterns in Qt development:

**The two critical fixes**:
1. Return null QPixmap (`QPixmap()`) instead of None or artificial pixmaps
2. Implement signal/slot system for async data updates with `dataChanged` emission

**The key insight**: Qt's model/view architecture requires explicit, properly-typed communication. Silent failures occur when Python-side logic doesn't match Qt's C++ expectations.

**Time investment**:
- 6 hours of debugging to identify root causes
- Multiple failed attempts before finding solutions
- Worth it: Resulted in fully stable, professional application

**Preventative measures**:
- Follow Qt's model/view protocols strictly
- Use signals/slots for all async operations
- Return proper Qt types (never None for images)
- Add extensive logging for debugging
- Test with minimal examples before full implementation

By following the patterns and avoiding the anti-patterns documented here, future Qt model/view implementations should be stable from the start, avoiding similar debugging pain.

---

## Quick Reference

### DOs ✅

- Return null QPixmap: `QPixmap()` for "no image"
- Emit `dataChanged` after updates
- Use signals for async operations
- Load QPixmaps from files in main thread
- Call `beginResetModel()` / `endResetModel()` when replacing data
- Validate indices before accessing data
- Log before operations, not just after

### DON'Ts ❌

- Don't return `None` for `Qt.DecorationRole`
- Don't create artificial QPixmaps with `QPixmap(w, h).fill()`
- Don't update data without emitting `dataChanged`
- Don't create QPixmaps in background threads
- Don't share QPixmap instances across items
- Don't rely on automatic view refresh
- Don't ignore Qt C++ crashes (add logging to find cause)

---

**Document Version**: 1.0
**Date**: 2026-01-09
**Status**: Complete - Application Fully Stable
**Author**: Debugging session with Claude Code
