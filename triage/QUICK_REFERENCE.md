# Qt Model/View Quick Reference Card

## The Two Critical Fixes for This Project

### Fix #1: Null QPixmap for Missing Images
```python
class MyModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._null_pixmap = QPixmap()  # isNull() == True

    def data(self, index, role):
        if role == Qt.DecorationRole:
            pixmap = self.cache.get(...)
            if pixmap is None or pixmap.isNull():
                return self._null_pixmap  # ✅ CORRECT
                # return None  # ❌ CRASHES
```

### Fix #2: Signal for Async Updates
```python
class Cache(QObject):
    data_ready = Signal(str)  # item_id

    def load_complete(self, item_id):
        self.data_ready.emit(item_id)

class MyModel(QAbstractListModel):
    def __init__(self, cache):
        super().__init__()
        cache.data_ready.connect(self._on_data_ready)

    def _on_data_ready(self, item_id):
        # Find row for item_id
        row = self._find_row(item_id)
        if row is not None:
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [Qt.DecorationRole])
```

---

## Common Patterns

### Model Reset Protocol
```python
def load_new_data(self, items):
    self.beginResetModel()  # ← Required
    self.items = items
    self.endResetModel()    # ← Required
```

### Single Item Update
```python
def update_item(self, row):
    index = self.index(row, 0)
    self.dataChanged.emit(index, index)  # All roles
    # Or specific role:
    self.dataChanged.emit(index, index, [Qt.DisplayRole])
```

### Range Update
```python
def update_range(self, first_row, last_row):
    top_left = self.index(first_row, 0)
    bottom_right = self.index(last_row, 0)
    self.dataChanged.emit(top_left, bottom_right)
```

---

## QPixmap Handling

### ✅ CORRECT
```python
# Load from file (main thread)
pixmap = QPixmap("/path/to/image.jpg")

# Null pixmap for "no image"
null_pixmap = QPixmap()  # isNull() == True

# Check before using
if not pixmap.isNull():
    painter.drawPixmap(x, y, pixmap)
```

### ❌ WRONG
```python
# Don't create artificial pixmaps
pixmap = QPixmap(100, 100)
pixmap.fill(Qt.gray)  # ← Will crash Qt rendering

# Don't return None for DecorationRole
return None  # ← Crashes

# Don't create QPixmap in worker thread
class Worker(QRunnable):
    def run(self):
        pixmap = QPixmap(...)  # ← Crash/undefined
```

---

## Signal/Slot Patterns

### Creating Signals
```python
from PySide6.QtCore import QObject, Signal

class MyClass(QObject):
    # Define signals as class attributes
    finished = Signal()
    progress = Signal(int)
    data_ready = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)  # ← Must call super().__init__()
```

### Connecting Signals
```python
# Connect to slot
obj.finished.connect(self.on_finished)

# Connect to lambda
obj.progress.connect(lambda p: print(f"Progress: {p}%"))

# Disconnect
obj.finished.disconnect(self.on_finished)
```

### Emitting Signals
```python
# Emit with no parameters
self.finished.emit()

# Emit with parameters (must match signal signature)
self.progress.emit(50)
self.data_ready.emit("item123", pixmap)
```

---

## Async Operations

### Worker Pattern
```python
from PySide6.QtCore import QRunnable, QObject, Signal, Slot

class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)

class Worker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.do_work()
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

# Usage
worker = Worker()
worker.signals.finished.connect(self.on_result)
QThreadPool.globalInstance().start(worker)
```

### Loading Images Async
```python
class ImageWorker(QRunnable):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.signals = WorkerSignals()

    def run(self):
        # Do file I/O in worker thread (thread-safe)
        from PIL import Image
        img = Image.open(self.file_path)
        img.thumbnail((256, 256))
        output_path = "/tmp/thumb.jpg"
        img.save(output_path)

        # Emit path, not QPixmap (QPixmap must be created in main thread)
        self.signals.finished.emit(output_path)

# In main thread
def on_worker_finished(self, output_path):
    # Create QPixmap in main thread
    pixmap = QPixmap(output_path)
    self.cache[key] = pixmap
    self.dataChanged.emit(...)
```

---

## Debugging Techniques

### Add Entry/Exit Logging
```python
def data(self, index, role):
    logger.info(f"data() ENTRY - row={index.row()}, role={role}")
    try:
        result = self.get_data(index, role)
        logger.info(f"data() returning: {type(result)}")
        return result
    except Exception as e:
        logger.error(f"data() ERROR: {e}", exc_info=True)
        return None
    finally:
        logger.info("data() EXIT")
```

### Binary Search for Crashes
```python
# Comment out half the code
def complex_function():
    step1()
    step2()
    # step3()  # ← Disabled
    # step4()  # ← Disabled
    # step5()  # ← Disabled

# If still crashes: problem in step1 or step2
# If works: problem in step3, step4, or step5
# Continue narrowing...
```

### Minimal Reproducible Example
```python
if __name__ == '__main__':
    # Test just the problematic part
    app = QApplication([])

    model = MyModel()
    model.items = [{'id': 'test', 'value': 123}]

    # Try to trigger crash
    index = model.index(0, 0)
    data = model.data(index, Qt.DisplayRole)
    print(f"Data: {data}")

    app.exec()
```

---

## Validation Checklist

Before committing model/view code:

- [ ] Model emits `dataChanged` after updates?
- [ ] Model uses `beginResetModel()` / `endResetModel()`?
- [ ] Model returns proper types (not `None` for images)?
- [ ] Model validates indices in `data()`?
- [ ] Cache/workers inherit from `QObject` with signals?
- [ ] Signals connected in `__init__()`?
- [ ] Signal handlers emit `dataChanged`?
- [ ] QPixmaps created only in main thread?
- [ ] Null QPixmap used for "no image"?
- [ ] Logging added at function entry?

---

## Common Errors and Solutions

### Error: Application crashes with no exception
**Cause**: Qt C++ crash, not Python exception
**Solution**: Add logging before every operation to find crash location

### Error: View doesn't update after data changes
**Cause**: Missing `dataChanged` signal
**Solution**: Emit `dataChanged` after modifying data

### Error: Crash when loading images
**Cause**: Returning `None` or artificial QPixmap for DecorationRole
**Solution**: Return null QPixmap: `QPixmap()`

### Error: "cannot import name 'QVariant'"
**Cause**: QVariant doesn't exist in Qt6/PySide6
**Solution**: Use Python types directly, null QPixmap for images

### Error: Async operations crash
**Cause**: Creating QPixmap in worker thread
**Solution**: Do file I/O in worker, create QPixmap in main thread

### Error: Random crashes during scrolling
**Cause**: Stale data, missing signals, state inconsistency
**Solution**: Implement proper signal/slot for async updates

---

## Performance Tips

### Virtual Scrolling
```python
# QListView already does virtual scrolling
view = QListView()
view.setUniformItemSizes(True)  # ← Improves performance
view.setLayoutMode(QListView.Batched)  # ← Lazy layout
```

### Caching
```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, max_size=500):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key):
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        # Evict oldest if over size
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
```

### Batch Updates
```python
# Bad: Emit signal for each item
for i in range(1000):
    self.update_item(i)
    self.dataChanged.emit(...)  # ← 1000 signals

# Good: Emit one signal for range
self.update_items_range(0, 999)
self.dataChanged.emit(first_index, last_index)  # ← 1 signal
```

---

## Qt6 vs Qt5 Changes

| Qt5/PySide2 | Qt6/PySide6 |
|-------------|-------------|
| `from PySide2` | `from PySide6` |
| `QVariant()` | Use Python types |
| `Qt.KeepAspectRatio` | `Qt.KeepAspectRatio` (same) |
| Implicit conversions | Explicit types needed |

---

## Resources

- [Qt Model/View Documentation](https://doc.qt.io/qt-6/model-view-programming.html)
- [PySide6 Reference](https://doc.qt.io/qtforpython-6/)
- [QAbstractItemModel](https://doc.qt.io/qt-6/qabstractitemmodel.html)
- [Signals and Slots](https://doc.qt.io/qt-6/signalsandslots.html)

---

**Keep this card handy when implementing Qt model/view architectures!**
