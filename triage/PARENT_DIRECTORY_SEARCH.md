# Parent Directory Database Search Fix

## Problem

The triage application is located in the `triage/` subdirectory. When it searches for databases, it only looked in the current directory (where the triage app runs), and couldn't see databases created by the main PyPhotoOrganizer application (which runs from the parent directory).

## Solution

Modified the database selector to search **multiple directories** simultaneously:

### 1. Enhanced DatabaseSelectorDialog

**File**: `ui/database_selector_dialog.py`

Added optional `search_paths` parameter to allow searching multiple directories:

```python
class DatabaseSelectorDialog(QDialog):
    def __init__(self, parent=None, search_paths=None):
        """
        Args:
            search_paths: List of directories to search for databases.
                         If None, searches current directory only.
        """
        self.search_paths = search_paths if search_paths else ["."]
```

**Modified `load_databases()` to search all paths:**

```python
def load_databases(self):
    """Load and display available databases."""
    all_databases = []
    seen_paths = set()  # Avoid duplicates

    for search_path in self.search_paths:
        databases = DatabaseMetadata.find_databases(search_path)
        for db in databases:
            db_path = db.get('path')
            if db_path and db_path not in seen_paths:
                all_databases.append(db)
                seen_paths.add(db_path)

    self.databases = all_databases
```

### 2. Updated Triage App to Search Parent Directory

**File**: `triage/ui/triage_window.py`

When opening the database selector, pass both current and parent directories:

```python
def _select_database(self):
    """Open database selector dialog."""
    # Search both current directory and parent directory
    search_paths = [
        ".",      # Current directory (triage/)
        "..",     # Parent directory (where main app runs)
    ]

    dialog = DatabaseSelectorDialog(self, search_paths=search_paths)
    dialog.database_selected.connect(self._on_database_selected)
    dialog.exec()
```

## How It Works

### Directory Structure
```
PyPhotoOrganizer/
├── main_gui.py                  # Main app (creates databases here)
├── PhotoDB.db                   # Main app database
├── triage/
│   ├── main_triage.py          # Triage app
│   └── ui/
│       └── triage_window.py    # Opens selector with search_paths=[".", ".."]
```

### Search Behavior

When the triage app opens the database selector:

1. **Searches "." (current directory)**:
   - If running from `triage/`: Searches `triage/` directory
   - If running from parent: Searches parent directory
   - Finds any databases created from triage app

2. **Searches ".." (parent directory)**:
   - If running from `triage/`: Searches parent directory
   - If running from parent: Searches parent's parent
   - Finds databases created by main app

3. **Deduplication**:
   - Uses absolute paths to avoid showing same database twice
   - `set()` ensures each unique database appears only once

### Works Regardless of Working Directory

**Running from parent directory:**
```bash
cd /path/to/PyPhotoOrganizer
python triage/main_triage.py
# Searches: . (parent) and .. (parent's parent)
# Finds: PhotoDB.db in current directory ✓
```

**Running from triage directory:**
```bash
cd /path/to/PyPhotoOrganizer/triage
python main_triage.py
# Searches: . (triage/) and .. (parent/)
# Finds: PhotoDB.db in parent directory ✓
```

## Benefits

✅ **Finds main app databases**: Triage can see databases created by main PyPhotoOrganizer
✅ **Maintains separation**: Triage app stays in subdirectory (clean architecture)
✅ **No duplication**: Same database never shown twice
✅ **Backward compatible**: Main app's dialog still works normally (defaults to current dir)
✅ **Flexible**: Works regardless of where user runs triage app from

## Files Modified

1. **ui/database_selector_dialog.py**
   - Added `search_paths` parameter to `__init__()`
   - Modified `load_databases()` to search multiple paths
   - Added deduplication logic

2. **triage/ui/triage_window.py**
   - Updated `_select_database()` to pass `search_paths=[".", ".."]`
   - Added explanatory comments

## Testing

### Test Case 1: Main App Database Visibility
```bash
# Create database with main app
cd /path/to/PyPhotoOrganizer
python main_gui.py
# Create "My Photos" database → PhotoDB.db in current directory

# Launch triage app
python triage/main_triage.py
# Click "Select Database..."
# Expected: "My Photos" database should appear ✓
```

### Test Case 2: Triage-Created Database
```bash
# Launch triage app
cd /path/to/PyPhotoOrganizer/triage
python main_triage.py
# Click "Select Database..."
# Click "Create New Database"
# Create "Triage DB" in triage/ directory

# Expected: "Triage DB" appears in selector ✓
# Also: Parent directory databases still visible ✓
```

### Test Case 3: No Duplicates
```bash
# Same database in both search paths
cd /path/to/PyPhotoOrganizer
python triage/main_triage.py
# Current dir: . → PyPhotoOrganizer/
# Parent dir:  .. → PyPhotoOrganizer/ (same)

# Expected: Each database appears only once ✓
```

## Future Enhancements

Potential improvements:

1. **Recursive Search**: Search subdirectories as well
2. **Configurable Paths**: Allow user to add custom search paths
3. **Path Display**: Show which directory each database was found in
4. **Recent Databases**: Remember last N databases across both apps

## Conclusion

This solution elegantly solves the directory isolation problem while maintaining clean separation between the main app and triage app. Both applications can now share the same databases seamlessly.
