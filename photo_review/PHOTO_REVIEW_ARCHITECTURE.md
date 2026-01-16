# Photo Review Architecture and API Reference

**Version 1.0.0**

This document provides technical documentation for the Photo Review application, including architecture overview, class reference, and integration points.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Module Structure](#module-structure)
3. [Class Reference](#class-reference)
4. [Database Integration](#database-integration)
5. [Signal/Slot Connections](#signalslot-connections)
6. [Integration with Main Application](#integration-with-main-application)
7. [Performance Considerations](#performance-considerations)
8. [Extending the Application](#extending-the-application)

---

## Architecture Overview

Photo Review follows a Model-View-Delegate (MVD) architecture pattern with Qt's signal/slot mechanism for component communication.

```
┌─────────────────────────────────────────────────────────────────┐
│                      PhotoReviewWindow                          │
│                    (Main Window/Controller)                     │
├─────────────┬───────────────────────────────────┬───────────────┤
│             │                                   │               │
│  QueryPanel │      PhotoGridView (View)         │ PreviewPanel  │
│   (Filter   │            │                      │  (ZoomableImage│
│    Builder) │            │                      │   Viewer)     │
│      │      │     PhotoGridModel (Model)        │               │
│      │      │            │                      │               │
│      │      │     PhotoGridDelegate             │               │
│      │      │       (Custom Rendering)          │               │
│      │      │                                   │               │
├──────┴──────┴───────────────────────────────────┴───────────────┤
│                                                                 │
│  PhotoQueryBuilder ←──── DatabaseMetadata ────→ ThumbnailCache  │
│    (SQL Generation)        (Schema/Settings)    (Three-Tier)    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Standalone Application**: Separate entry point from main GUI for focused photo review workflow

2. **Virtual Scrolling**: Only visible thumbnails are rendered, enabling 10,000+ item support

3. **Three-Tier Thumbnail Cache**: Memory → Disk → Generation pipeline for fast loading

4. **Query-Based Selection**: SQL-driven filtering instead of loading entire archive

5. **Component Reuse**: Leverages existing workers (delete, rotate) and dialogs from main application

---

## Module Structure

```
photo_review/
├── __init__.py              # Package initialization, version info
├── review_window.py         # Main window class (PhotoReviewWindow)
├── query_panel.py           # Left sidebar with filters (QueryPanel)
├── query_builder.py         # SQL query generation (PhotoQueryBuilder)
├── photo_grid_model.py      # Data model for grid (PhotoGridModel)
├── photo_grid_view.py       # Grid widget with selection (PhotoGridView)
├── photo_grid_delegate.py   # Custom item rendering (PhotoGridDelegate)
├── PHOTO_REVIEW_USER_GUIDE.md    # User documentation
└── PHOTO_REVIEW_ARCHITECTURE.md  # This file
```

### Entry Point

```python
# photo_review.py (in parent directory)
from photo_review.review_window import PhotoReviewWindow

app = QApplication(sys.argv)
window = PhotoReviewWindow()
window.show()
sys.exit(app.exec())
```

---

## Class Reference

### PhotoReviewWindow

**File**: `review_window.py`

Main application window that coordinates all components.

```python
class PhotoReviewWindow(QMainWindow):
    """Main window for Photo Review application."""
```

#### Constructor

```python
def __init__(self, splash_callback=None):
    """
    Initialize Photo Review window.

    Args:
        splash_callback: Optional callable for splash screen updates
    """
```

#### Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `current_database_path` | `str` | Path to active database |
| `database_metadata` | `DatabaseMetadata` | Database operations |
| `thumbnail_cache` | `ThumbnailCache` | Thumbnail management |
| `query_panel` | `QueryPanel` | Filter controls |
| `grid_view` | `PhotoGridView` | Thumbnail grid widget |
| `grid_model` | `PhotoGridModel` | Grid data model |
| `preview_panel` | `QWidget` | Bottom preview panel |
| `detached_preview` | `DetachablePreviewWindow` | Floating preview window |

#### Key Methods

| Method | Description |
|--------|-------------|
| `set_database(path)` | Load database and initialize UI |
| `on_query_executed(results)` | Handle query results |
| `delete_selected()` | Delete selected files to vault |
| `rotate_selected()` | Open rotation dialog |
| `correct_date_selected()` | Open date correction dialog |
| `run_current_query()` | Re-execute current query |

---

### QueryPanel

**File**: `query_panel.py`

Left sidebar with all filtering controls.

```python
class QueryPanel(QWidget):
    """Left panel with query builder and folder browser."""

    # Signals
    query_executed = Signal(list)  # Emits matching records
    folder_selected = Signal(str)  # Emits folder path
```

#### Constructor

```python
def __init__(self, db_metadata, db_path: str, parent=None):
    """
    Initialize query panel.

    Args:
        db_metadata: DatabaseMetadata instance
        db_path: Path to database file
        parent: Parent widget
    """
```

#### Key Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_current_filters()` | `() -> Dict[str, Any]` | Get current filter settings |
| `set_filters(filters)` | `(Dict[str, Any]) -> None` | Apply filter configuration |
| `clear_filters()` | `() -> None` | Reset all filters |
| `execute_query()` | `() -> None` | Execute query and emit results |
| `save_current_query()` | `() -> None` | Save current filters as named query |

#### Filter Dictionary Structure

```python
{
    # Text search
    'search_text': str,              # Full-text search term

    # Date filters
    'creation_date_from': str,       # YYYY-MM-DD
    'creation_date_to': str,         # YYYY-MM-DD
    'correction_date_from': str,     # YYYY-MM-DD
    'correction_date_to': str,       # YYYY-MM-DD

    # Version filter
    'version_filter': str,           # 'current', 'all', 'prior'

    # Status filters
    'has_unreliable_date': bool,
    'has_corrected_date': bool,      # Can be True, False, or absent
    'needs_reorganization': bool,
    'has_revisions': bool,

    # Pattern filters
    'filename_pattern': str,         # Substring match
    'folder_path': str,              # Folder prefix match
}
```

---

### PhotoQueryBuilder

**File**: `query_builder.py`

Generates parameterized SQL queries from filter dictionaries.

```python
class PhotoQueryBuilder:
    """Builds SQL queries for UniquePhotos table with various filters."""
```

#### Constructor

```python
def __init__(self, db_path: str):
    """
    Initialize query builder.

    Args:
        db_path: Path to SQLite database
    """
```

#### Key Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `build_query(filters)` | `(Dict) -> Tuple[str, List]` | Build SQL and params |
| `execute_query(filters, limit, offset)` | `(Dict, int, int) -> List[Dict]` | Execute and return results |
| `count_results(filters)` | `(Dict) -> int` | Count matching records |
| `get_archive_folders()` | `() -> List[Dict]` | Get folder structure |
| `get_months_in_year(year)` | `(str) -> List[Dict]` | Get months with photos |
| `get_days_in_month(year, month)` | `(str, str) -> List[Dict]` | Get days with photos |

#### Query Result Record Structure

```python
{
    'file_hash': str,              # SHA-256 hash
    'archive_path': str,           # Path in archive (file_name column)
    'source_path': str,            # Original source path
    'create_datetime': str,        # Full datetime string
    'create_year': str,            # Year component
    'create_month': str,           # Month component
    'create_day': str,             # Day component
    'file_size': int,              # Size in bytes
    'revised_photo': str,          # Parent revision hash (or None)
    'corrected_date': str,         # Corrected date (or None)
    'needs_reorganization': int,   # 1 if needs reorganization
    'flag_reason': str,            # Why flagged (or None)
    'date_source': str,            # 'exif', 'os_metadata', etc.
    'original_date': str,          # Original detected date
}
```

---

### PhotoGridModel

**File**: `photo_grid_model.py`

Qt data model for the thumbnail grid.

```python
class PhotoGridModel(QAbstractListModel):
    """Data model for photo thumbnail grid."""

    # Custom roles
    RecordRole = Qt.UserRole + 100   # Full record dict
    StatusRole = Qt.UserRole + 101   # Status for overlay
    HashRole = Qt.UserRole + 102     # File hash
    PathRole = Qt.UserRole + 103     # Archive path

    # Signal
    data_loaded = Signal(int)  # Emits record count
```

#### Constructor

```python
def __init__(self, thumbnail_cache, parent=None):
    """
    Initialize model.

    Args:
        thumbnail_cache: ThumbnailCache instance
        parent: Parent QObject
    """
```

#### Key Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `load_data(records)` | `(List[Dict]) -> None` | Load query results |
| `get_record_at(index)` | `(QModelIndex) -> Dict` | Get record at index |
| `get_record_by_hash(hash)` | `(str) -> Dict` | Find record by hash |
| `set_thumbnail_size(size)` | `(int) -> None` | Change thumbnail size |
| `refresh_thumbnail(hash)` | `(str) -> None` | Force thumbnail reload |
| `remove_items(hashes)` | `(List[str]) -> None` | Remove items from model |
| `update_item(hash, updates)` | `(str, Dict) -> None` | Update item data |

#### Data Roles

| Role | Returns | Description |
|------|---------|-------------|
| `Qt.DisplayRole` | `str` | Filename |
| `Qt.DecorationRole` | `QPixmap` | Thumbnail image |
| `Qt.ToolTipRole` | `str` | Multi-line tooltip |
| `RecordRole` | `Dict` | Full record data |
| `StatusRole` | `str` | Status identifier |
| `HashRole` | `str` | File hash |
| `PathRole` | `str` | Archive path |

#### Status Values

| Status | Description |
|--------|-------------|
| `'normal'` | No special status |
| `'unreliable'` | Has unreliable date flag |
| `'corrected'` | Date corrected, needs reorganization |
| `'reorganized'` | Fully processed |
| `'revision'` | Has parent revision (was rotated) |

---

### PhotoGridView

**File**: `photo_grid_view.py`

QListView subclass with grid display and interaction handling.

```python
class PhotoGridView(QListView):
    """Thumbnail grid for photo review."""

    # Signals
    selection_changed = Signal(list)      # List of selected hashes
    item_activated = Signal(dict)         # Double-click/Space record
    delete_requested = Signal()           # Context menu delete
    rotate_requested = Signal()           # Context menu rotate
    correct_date_requested = Signal()     # Context menu correct
    open_file_requested = Signal()        # Context menu open
    open_folder_requested = Signal()      # Context menu folder
    copy_path_requested = Signal()        # Context menu copy
    refresh_thumbnail_requested = Signal()  # Context menu refresh
    deselect_all_requested = Signal()     # Context menu deselect
```

#### Constructor

```python
def __init__(self, model, parent=None):
    """
    Initialize grid view.

    Args:
        model: PhotoGridModel instance
        parent: Parent widget
    """
```

#### Key Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `set_thumbnail_size(name)` | `(str) -> None` | 'small', 'medium', 'large' |
| `set_thumbnail_size_pixels(px)` | `(int) -> None` | Set by pixel size |
| `get_selected_items()` | `() -> List[Dict]` | Get all selected records |
| `get_selected_hashes()` | `() -> List[str]` | Get selected file hashes |

#### Keyboard Shortcuts (Built-in)

| Key | Action |
|-----|--------|
| `1`, `2`, `3` | Set thumbnail size |
| `Space` | Emit item_activated for selected |
| `Escape` | Clear selection |
| `Ctrl+A` | Select all |
| `Delete` | Emit delete_requested |
| `Ctrl+R` | Emit rotate_requested |
| `Ctrl+D` | Emit correct_date_requested |
| `Ctrl+O` | Emit open_file_requested |
| `Ctrl+E` | Emit open_folder_requested |

---

### PhotoGridDelegate

**File**: `photo_grid_delegate.py`

Custom rendering for grid items.

```python
class PhotoGridDelegate(QStyledItemDelegate):
    """Delegate for rendering photo review thumbnails."""

    STATUS_COLORS = {
        'corrected': QColor(0, 150, 0, 220),      # Green
        'reorganized': QColor(50, 150, 255, 220),  # Blue
        'unreliable': QColor(255, 180, 0, 220),    # Yellow
        'revision': QColor(180, 0, 255, 220),      # Purple
        'normal': None
    }

    STATUS_SYMBOLS = {
        'corrected': '!',
        'reorganized': '✓',
        'unreliable': '?',
        'revision': 'R',
        'normal': ''
    }
```

#### Key Methods

| Method | Description |
|--------|-------------|
| `paint(painter, option, index)` | Render item with thumbnail and overlay |
| `sizeHint(option, index)` | Return item size |
| `set_thumbnail_size(size)` | Update thumbnail size |

---

## Database Integration

### Tables Used

| Table | Purpose |
|-------|---------|
| `UniquePhotos` | Main photo records |
| `UnreliableDates` | Date flag and correction tracking |
| `DeletedFiles` | Soft-delete tracking |
| `SavedQueries` | Saved query configurations |
| `DatabaseMetadata` | Application state (photo_review_state) |

### Key Queries

#### Main Photo Query (with all filters)

```sql
SELECT
    up.file_hash,
    up.file_name as archive_path,
    up.source_path,
    up.create_datetime,
    up.create_year,
    up.create_month,
    up.create_day,
    up.file_size,
    up.revised_photo,
    ud.corrected_date,
    ud.needs_reorganization,
    ud.flag_reason,
    ud.date_source,
    ud.original_date
FROM UniquePhotos up
LEFT JOIN UnreliableDates ud ON up.file_hash = ud.file_hash
LEFT JOIN DeletedFiles df ON up.file_hash = df.file_hash AND df.is_restored = 0
WHERE df.file_hash IS NULL
  -- Additional filter conditions added dynamically
ORDER BY up.create_year DESC, up.create_month DESC, up.create_day DESC
```

#### Version Filter Conditions

```sql
-- Current versions only (default)
AND up.file_name LIKE '/path/to/main/archive%'
AND up.file_name NOT LIKE '/path/to/prior/archive%'

-- Prior versions only
AND up.file_name LIKE '/path/to/prior/archive%'

-- All versions: no additional condition
```

### DatabaseMetadata Methods Used

| Method | Purpose |
|--------|---------|
| `get_archive_location()` | Main archive path |
| `get_prior_revision_archive_location()` | Prior revision path |
| `get_delete_vault_location()` | Delete vault path |
| `get_saved_queries()` | Load saved queries |
| `save_query(name, filters)` | Save new query |
| `get_photo_review_state()` | Restore last session |
| `set_photo_review_state(state)` | Save session state |
| `get_thumbnail_cache_dir()` | Thumbnail cache location |

---

## Signal/Slot Connections

### Main Window Connections

```python
# Query Panel → Window
query_panel.query_executed.connect(on_query_executed)
query_panel.folder_selected.connect(on_folder_selected)

# Grid Model → Window
grid_model.data_loaded.connect(on_data_loaded)

# Grid View → Window
grid_view.selection_changed.connect(on_selection_changed)
grid_view.item_activated.connect(on_item_activated)
grid_view.delete_requested.connect(delete_selected)
grid_view.rotate_requested.connect(rotate_selected)
grid_view.correct_date_requested.connect(correct_date_selected)
grid_view.open_file_requested.connect(open_selected_file)
grid_view.open_folder_requested.connect(open_selected_folder)
grid_view.copy_path_requested.connect(copy_selected_path)
grid_view.refresh_thumbnail_requested.connect(refresh_selected_thumbnails)
grid_view.deselect_all_requested.connect(deselect_all)

# Thumbnail Cache → Model
thumbnail_cache.thumbnail_ready.connect(model._on_thumbnail_ready)
```

### Data Flow

```
User Filter Change
       │
       ▼
   QueryPanel
       │
       │ get_current_filters()
       ▼
 PhotoQueryBuilder
       │
       │ build_query() → execute_query()
       ▼
   SQL Results
       │
       │ query_executed.emit(results)
       ▼
 PhotoReviewWindow
       │
       │ grid_model.load_data(results)
       ▼
  PhotoGridModel
       │
       │ data_loaded.emit(count)
       │ dataChanged.emit() (for visible items)
       ▼
  PhotoGridView
       │
       │ Requests thumbnails via DecorationRole
       ▼
  ThumbnailCache
       │
       │ thumbnail_ready.emit(hash, size, path)
       ▼
  PhotoGridModel
       │
       │ dataChanged.emit() (specific item)
       ▼
  PhotoGridDelegate
       │
       │ paint() renders thumbnail
       ▼
     Display
```

---

## Integration with Main Application

### Shared Components

The Photo Review application reuses these components from the main UI:

| Component | Location | Purpose |
|-----------|----------|---------|
| `DeleteWorker` | `ui/delete_worker.py` | Background file deletion |
| `RotateWorker` | `ui/rotate_worker.py` | Background image rotation |
| `DateCorrectionDialog` | `ui/date_correction_dialog.py` | Date input UI |
| `RotateImageDialog` | `ui/rotate_image_dialog.py` | Rotation angle selection |
| `DetachablePreviewWindow` | `ui/detachable_preview_window.py` | Large preview |
| `ZoomableImageViewer` | `ui/date_corrections_tab.py` | Zoomable preview widget |
| `ThumbnailCache` | `triage/thumbnail_cache.py` | Three-tier caching |
| `DatabaseMetadata` | `database_metadata.py` | Database operations |

### Database Compatibility

Photo Review uses the same database schema as the main application:
- Works with databases created by main app
- Changes made in Photo Review visible in main app
- Settings stored in same DatabaseMetadata table

---

## Performance Considerations

### Virtual Scrolling

The grid uses Qt's batched layout mode:

```python
self.setUniformItemSizes(True)  # All items same size
self.setLayoutMode(QListView.Batched)  # Lazy layout
self.setBatchSize(50)  # Layout 50 items at a time
```

### Thumbnail Loading Strategy

1. **Memory Cache**: 500 most recent thumbnails in RAM
2. **Disk Cache**: Up to 5GB of thumbnails on disk
3. **Generation**: 8 worker threads for parallel generation

### Query Limits

Default limit of 5,000 records per query:
- Prevents memory issues with large archives
- Use filters to narrow results
- Pagination available via offset parameter

### Model Reset Safety

The model uses a safety flag during reset:

```python
self._is_resetting = True
self.beginResetModel()
self.file_items = records
self.endResetModel()
self._is_resetting = False
```

This prevents Qt crashes from accessing data during model reset.

---

## Extending the Application

### Adding a New Filter

1. **Add UI Control** in `QueryPanel._init_ui()`:
```python
self.my_filter_cb = QCheckBox("My Filter")
status_layout.addWidget(self.my_filter_cb)
```

2. **Update `get_current_filters()`**:
```python
if self.my_filter_cb.isChecked():
    filters['my_filter'] = True
```

3. **Update `set_filters()`**:
```python
if filters.get('my_filter'):
    self.my_filter_cb.setChecked(True)
```

4. **Update `clear_filters()`**:
```python
self.my_filter_cb.setChecked(False)
```

5. **Add SQL Condition** in `PhotoQueryBuilder.build_query()`:
```python
if filters.get('my_filter'):
    conditions.append("up.some_column = ?")
    params.append(some_value)
```

### Adding a New Action

1. **Add Menu Item** in `PhotoReviewWindow._create_menu_bar()`:
```python
my_action = QAction("&My Action", self)
my_action.setShortcut("Ctrl+M")
my_action.triggered.connect(self.my_action_handler)
actions_menu.addAction(my_action)
```

2. **Add Signal** to `PhotoGridView` (if context menu needed):
```python
my_action_requested = Signal()
```

3. **Add Context Menu Item** in `PhotoGridView._show_context_menu()`:
```python
my_action = QAction("My Action", self)
my_action.triggered.connect(lambda: self.my_action_requested.emit())
menu.addAction(my_action)
```

4. **Implement Handler** in `PhotoReviewWindow`:
```python
def my_action_handler(self):
    selected = self.grid_view.get_selected_items()
    if not selected:
        return
    # Perform action
```

5. **Connect Signal** in `PhotoReviewWindow._connect_signals()`:
```python
self.grid_view.my_action_requested.connect(self.my_action_handler)
```

### Adding a New Status Overlay

1. **Add Status Logic** in `PhotoGridModel._get_status()`:
```python
elif item.get('my_condition'):
    return 'my_status'
```

2. **Add Color and Symbol** in `PhotoGridDelegate`:
```python
STATUS_COLORS = {
    ...
    'my_status': QColor(255, 0, 128, 220),  # Pink
}

STATUS_SYMBOLS = {
    ...
    'my_status': 'M',
}
```

3. **Update Tooltip** in `PhotoGridModel._build_tooltip()`:
```python
status_text = {
    ...
    'my_status': 'My status description',
}.get(status, status)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01 | Initial release with full feature set |
