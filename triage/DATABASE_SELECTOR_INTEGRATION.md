# Database Selector Integration for Triage Application

## Overview

The triage application now uses the same database selection UI and logic as the main PyPhotoOrganizer application, providing a consistent user experience across both applications.

## Changes Made

### 1. Replaced Simple Database Selection

**Before:**
- Simple QComboBox dropdown with database names
- Basic QFileDialog for browsing
- Manual database list refresh

**After:**
- Full `DatabaseSelectorDialog` from main application
- Shows database metadata (name, archive location, photo count)
- Create new database button
- Archive location validation
- Professional UI with detailed information panel

### 2. Files Modified

#### ui/database_selector_dialog.py (Main App)
**Added:**
```python
def __init__(self, parent=None, search_paths=None):
    """Initialize with optional search paths."""
    self.search_paths = search_paths if search_paths else ["."]
```

**Modified:**
```python
def load_databases(self):
    # Search all configured paths
    all_databases = []
    seen_paths = set()  # Avoid duplicates

    for search_path in self.search_paths:
        databases = DatabaseMetadata.find_databases(search_path)
        # Deduplicate by absolute path
        ...
```

#### triage/ui/triage_window.py
**Imports:**
- Added: `from ui.database_selector_dialog import DatabaseSelectorDialog`
- Removed: `QComboBox` (no longer needed)

**Toolbar Changes:**
```python
# Old: QComboBox with database list
self.db_combo = QComboBox()

# New: Label showing current database name
self.db_name_label = QLabel("No database loaded")
select_db_btn = QPushButton("Select Database...")
```

**Methods Updated:**
- `_select_database()`: Now opens `DatabaseSelectorDialog` with custom search paths:
  ```python
  search_paths = [".", ".."]  # Current and parent directories
  dialog = DatabaseSelectorDialog(self, search_paths=search_paths)
  ```
- `_on_database_selected()`: New method to handle database selection from dialog
- `_load_database()`: Now updates `db_name_label` and saves to config
- Removed: `_refresh_database_list()`, `_on_database_changed()`

#### triage/triage_config.py
**Added:**
```python
@database_path.setter
def database_path(self, value: str):
    """Set database path."""
    self.config['database_path'] = value
```
This allows the triage window to save the selected database path to the configuration file.

### 3. User Experience Improvements

#### Database Selection Flow
1. User clicks "Select Database..." button
2. DatabaseSelectorDialog opens showing:
   - List of all available databases
   - Database information panel with:
     - Name and description
     - Archive location
     - Creation date
     - Last used date
     - Total photo count
     - Database file path
3. User can:
   - Select existing database (double-click or "Open Selected")
   - Create new database (opens CreateDatabaseDialog)
   - Cancel operation
4. Selected database loads automatically
5. Database path saved to config for next session

#### Archive Location Validation
- Validates archive folder exists before loading database
- Shows warning if archive location missing
- Allows user to proceed anyway (with option to update location later)

#### Persistent Configuration
- Last used database automatically loaded on startup
- Database path saved to `triage_config.json` when changed
- Consistent behavior with main application

### 4. Benefits

✅ **Consistency**: Same UI/UX as main PyPhotoOrganizer application
✅ **Better Information**: Shows all database metadata before opening
✅ **Validation**: Checks archive location exists before loading
✅ **Creation**: Can create new databases directly from triage app
✅ **Discovery**: Automatically finds all databases in common locations
✅ **Professional**: Clean, polished interface

### 5. Technical Details

#### Database Discovery

**Multi-Directory Search:**
The triage app searches multiple locations to find databases:
```python
search_paths = [
    ".",      # Current directory (triage/)
    "..",     # Parent directory (where main app runs)
]
```

This ensures the triage app can find:
- Databases created by the main PyPhotoOrganizer app (in parent directory)
- Databases created from the triage app itself (in current directory)
- Works regardless of where you run the triage app from

**DatabaseSelectorDialog Enhancement:**
The dialog now accepts optional `search_paths` parameter:
```python
def __init__(self, parent=None, search_paths=None):
    """
    Args:
        search_paths: List of directories to search for databases.
                     If None, searches current directory only.
    """
```

**Duplicate Prevention:**
The dialog automatically deduplicates databases found in multiple search paths using absolute path comparison.

#### Signal/Slot Pattern
```python
dialog = DatabaseSelectorDialog(self)
dialog.database_selected.connect(self._on_database_selected)
dialog.exec()
```

This ensures the dialog properly communicates back to the main window when a database is selected.

## Testing Checklist

- [x] Syntax validation (both files compile without errors)
- [ ] Database selection dialog opens correctly
- [ ] Existing databases displayed with metadata
- [ ] Database selection loads and initializes cache
- [ ] Database name displayed in toolbar
- [ ] Archive location validation works
- [ ] Create new database from triage app
- [ ] Last used database loads on startup
- [ ] Database path saved to config

## Future Enhancements

Potential improvements for future versions:

1. **Recent Databases**: Show most recently used databases at top
2. **Database Search**: Filter database list by name or location
3. **Database Groups**: Organize databases by category or project
4. **Quick Switch**: Keyboard shortcut to switch databases
5. **Database Info**: Hover tooltip showing quick stats

## Compatibility

- **Requires**: Main PyPhotoOrganizer database selector modules
- **Location**: `ui/database_selector_dialog.py` and `ui/create_database_dialog.py`
- **Works With**: All existing PyPhotoOrganizer databases
- **Backward Compatible**: Old triage_config.json files still work

## Summary

The triage application now provides a professional, consistent database selection experience that matches the main application. Users benefit from better information visibility, validation, and the ability to create new databases directly from the triage interface.
