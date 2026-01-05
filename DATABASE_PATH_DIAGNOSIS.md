# Database Path Mismatch Diagnosis

## Problem Statement

File rename settings appear enabled in the Settings tab checkbox, but during processing, the database shows rename as disabled. This suggests that the Settings tab is saving to one database while processing is reading from a different database.

## Diagnostic Logging Added

I've added comprehensive logging at every point where `database_path` is used or passed. When you run the application, the logs will show exactly which database file each component is using.

### Logging Points Added:

1. **config.py (lines 92-100)**
   - Logs when Config object is created from settings_dict
   - Shows DEFAULTS database_path, settings_dict database_path, and FINAL database_path
   - This proves whether the Config class correctly receives and stores the database path

2. **config.py (line 328)**
   - Logs when database_path property is accessed
   - Shows what value is being returned when worker/main.py requests the database path

3. **ui/main_window.py (lines 163-168)** [already existed]
   - Logs self.current_database_path before setting config['database_path']
   - Shows which database the GUI thinks is active

4. **ui/settings_tab.py (lines 814-820)** [already existed]
   - Logs database path when set_database() is called
   - Shows which database the Settings tab is connected to

5. **main.py (lines 178-180)** [already existed]
   - Logs database_path parameter when creating DatabaseMetadata
   - Shows which database the processing code is using

6. **database_metadata.py** [already existed]
   - Comprehensive logging in is_file_rename_enabled() and set_file_rename_enabled()
   - Shows which database file is being read from / written to

## Test Script Created

Created `test_database_path.py` which simulates the complete flow:
- Settings tab returns config with DEFAULT database path
- Main window overrides with selected database path
- Worker creates Config object from dictionary
- Config object accesses database_path property

**Test Result**: ✓ SUCCESS - The Config class correctly handles database_path from settings_dict.

This proves the architecture is sound.

## How to Use This Diagnosis

### Step 1: Run the Application

Start PyPhotoOrganizer normally.

### Step 2: Enable File Renaming

1. Go to the Settings tab
2. Check the "Enable file renaming" checkbox
3. **Watch the logs** - you'll see:
   ```
   SETTINGS TAB: set_database() called
     Database path: '/path/to/SomeDatabase.db'

   → on_rename_enabled_changed called...
     Checkbox.isChecked() = True

   DATABASE_METADATA: set_file_rename_enabled(True)
     Database path: '/path/to/SomeDatabase.db'
   ✓ File renaming ENABLED successfully
   ```

4. **Note which database path** the Settings tab is using

### Step 3: Start Processing

1. Go to the Setup tab
2. Select some source files
3. Click "Start Processing"
4. **Watch the logs** - you'll see:
   ```
   MAIN_WINDOW: Setting config database_path
     self.current_database_path = '/path/to/SomeDatabase.db'
     config['database_path'] = '/path/to/SomeDatabase.db'

   CONFIG: Creating from settings_dict
     DEFAULTS database_path: 'PhotoDB.db'
     settings_dict database_path: '/path/to/SomeDatabase.db'
     FINAL _settings database_path: '/path/to/SomeDatabase.db'

   CONFIG.database_path property accessed → returning: '/path/to/SomeDatabase.db'

   MAIN.PY: Creating DatabaseMetadata with database_path: '/path/to/SomeDatabase.db'

   File rename enabled: True (or False)
   ```

5. **Note which database path** the processing code is using

### Step 4: Compare the Paths

**If the paths match:**
- Settings tab: `/path/to/DatabaseA.db`
- Processing:     `/path/to/DatabaseA.db`
- **Result**: Both components are using the same database
- **Issue**: Something else is wrong (not a path mismatch)

**If the paths differ:**
- Settings tab: `/path/to/DatabaseA.db`
- Processing:     `/path/to/DatabaseB.db`
- **Result**: This is the bug! Settings saves to DatabaseA, processing reads from DatabaseB
- **Fix**: We need to ensure both use the same database path

## Expected Log Output (Example)

When everything works correctly, you should see:

```
================================================================================
SETTINGS TAB: set_database() called
  Database path: '/home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db'
================================================================================

[User clicks checkbox]

→ on_rename_enabled_changed called - RAW state value: 2 (type: <class 'int'>)
  Qt.Checked = 2, Qt.Unchecked = 0
  Checkbox.isChecked() = True
  State comparison (state == Qt.Checked) = True
  Calling set_file_rename_enabled(True)...

→ DATABASE_METADATA.set_file_rename_enabled(True) called for database: /home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db
✓ File rename ENABLED successfully (rows updated: 1)
  Verification: enable_file_rename = 1

[User starts processing]

================================================================================
MAIN_WINDOW: Setting config database_path
  self.current_database_path = '/home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db'
  config['database_path'] = '/home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db'
================================================================================

================================================================================
CONFIG: Creating from settings_dict
  DEFAULTS database_path: 'PhotoDB.db'
  settings_dict database_path: '/home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db'
  FINAL _settings database_path: '/home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db'
================================================================================

CONFIG.database_path property accessed → returning: '/home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db'

================================================================================
MAIN.PY: Creating DatabaseMetadata with database_path: '/home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db'
================================================================================

→ DATABASE_METADATA.is_file_rename_enabled() called for database: /home/doug/Dropbox/Projects/python Projects/PyPhotoOrganizer/PyPhotoOrganizer/PhotoDB_Test24DB.db
✓ File rename is ENABLED (enable_file_rename=1)

File rename enabled: True
```

## What to Look For

1. **Database paths must match** across all components
2. **Settings tab** should log the same database path when saving
3. **Main window** should log the same database path in config
4. **Config object** should show the same path in FINAL _settings
5. **Main.py** should receive the same database path parameter
6. **DatabaseMetadata.is_file_rename_enabled()** should read from the same database

## Next Steps After Diagnosis

Once you run this and share the logs, we'll see exactly where the path diverges and can fix the issue immediately.
