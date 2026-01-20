# PRD: Album Association for Import Source Directories

## Overview

Add the ability to optionally associate an album with each import source directory. When an album is specified, all files imported from that source are automatically added to the album in addition to being copied to the archive. An additional option allows creating sub-albums for each subdirectory in the import location.

---

## User Stories

1. **As a user**, I want to associate an album with a source directory so that all photos from my phone automatically go into a "Phone Photos" album during import.

2. **As a user**, I want the option to create sub-albums for subdirectories so that my "Phone Photos" album can have separate sub-albums for "Camera Roll", "Screenshots", "WhatsApp", etc.

3. **As a user**, I want album additions to happen automatically during import so I don't have to manually add photos to albums after each import.

---

## Functional Requirements

### FR1: Album Association for Source Directories

- Each source directory can optionally specify an album
- Album selection via dropdown in the source directory table
- Selection persists in database and survives application restart
- "(None)" option available to disable album association

### FR2: Automatic Album Addition During Import

- When a source has an album association, every file imported from that source is added to the specified album
- Album addition happens after successful archive copy (non-blocking)
- Files are copied to both archive AND album storage (separate copies)
- Failures in album addition do not prevent archive import from completing

### FR3: Sub-Album Creation for Subdirectories

- Optional checkbox per source directory: "Create sub-albums for subdirectories"
- Only enabled when an album is selected
- Creates/uses sub-albums based on subdirectory structure
- **Unlimited depth**: All subdirectory levels create corresponding sub-albums
- Sub-albums are created on-demand (only when files are imported)

### FR4: Sub-Album Naming Convention

**Pattern:** `{Parent Album} - {Subdir1} - {Subdir2} - ...`

**Examples:**
| Source Path | Subdirectory | Sub-Album Name |
|-------------|--------------|----------------|
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/Camera Roll` | "Phone - Camera Roll" |
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/Screenshots` | "Phone - Screenshots" |
| `/Photos/Phone` (Album: "Phone") | `/Photos/Phone/Camera/2024/Jan` | "Phone - Camera - 2024 - Jan" |

### FR5: Sub-Album Storage Location

- Sub-albums stored as subfolders under parent album's storage location
- Example: Parent at `/Albums/Phone/` → Sub-album at `/Albums/Phone/Camera Roll/`
- Directory created automatically if it doesn't exist

---

## Non-Functional Requirements

### NFR1: Performance

- Album addition should not significantly slow down import
- Album operations are secondary to archive copy (continue on album failure)

### NFR2: Data Integrity

- Source files remain protected (read-only)
- Archive copy completes independently of album operations
- Album failures logged but do not abort import

### NFR3: Consistency

- Use existing AlbumManager API for all album operations
- Follow existing database patterns (WAL mode, auto-upgrade)
- Match existing UI styling and patterns

---

## Technical Design

### Database Schema Changes

**SourceDirectories table - Add 2 columns:**

```sql
album_id INTEGER,                    -- FK to Albums.id, NULL = no association
enable_sub_albums INTEGER DEFAULT 0  -- 0 = disabled, 1 = enabled
```

**New table - SourceDirectorySubAlbums:**

```sql
CREATE TABLE SourceDirectorySubAlbums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_directory_id INTEGER NOT NULL,
    parent_album_id INTEGER NOT NULL,
    sub_album_id INTEGER NOT NULL,
    relative_subdir_path TEXT NOT NULL,
    created_timestamp TEXT NOT NULL,
    FOREIGN KEY (source_directory_id) REFERENCES SourceDirectories(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_album_id) REFERENCES Albums(id) ON DELETE CASCADE,
    FOREIGN KEY (sub_album_id) REFERENCES Albums(id) ON DELETE CASCADE,
    UNIQUE(source_directory_id, relative_subdir_path)
);
```

### UI Changes

**Source Directory Table - Add 2 columns:**

| Column | Type | Behavior |
|--------|------|----------|
| Album | QComboBox | Dropdown with "(None)" + all albums |
| Sub-Albums | QCheckBox | Enabled only when album selected |

### Import Flow Integration

**Hook point:** `main.py:organize_files()` after successful file copy (around line 506)

```
For each file:
1. Copy to archive (existing)
2. Update database (existing)
3. NEW: If source has album association:
   a. If sub-albums disabled: add to parent album
   b. If sub-albums enabled:
      - Determine sub-album from relative path
      - Get or create sub-album
      - Add to sub-album
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `database_metadata.py` | Add columns to SourceDirectories, new SourceDirectorySubAlbums table, getter/setter methods |
| `ui/import_settings_tab.py` | Add Album dropdown and Sub-Albums checkbox columns to source table |
| `main.py` | Add album integration in `organize_files()` after file copy |
| `ui/worker.py` | Initialize AlbumManager, build source-album map, pass to organize_files() |

---

## Edge Cases & Error Handling

| Scenario | Handling |
|----------|----------|
| Album storage unavailable | Log warning, skip album add, continue archive import |
| Album deleted mid-import | Check album exists before add, skip if deleted |
| Sub-album name collision | Use existing album if same source, otherwise append unique suffix |
| Empty subdirectories | No sub-album created (only created when files exist) |
| Source removed from config | Files already have full path, matching still works |

---

## Implementation Phases

### Phase 1: Database Schema
- Add `album_id` and `enable_sub_albums` columns to SourceDirectories
- Add getter/setter methods in DatabaseMetadata
- Create SourceDirectorySubAlbums table
- Auto-upgrade migration logic

### Phase 2: UI - Album Selection
- Add Album dropdown column to source table
- Populate from AlbumManager.get_all_albums()
- Save/load album association on change
- Refresh dropdowns when albums change

### Phase 3: UI - Sub-Albums Checkbox
- Add Sub-Albums checkbox column
- Enable/disable based on album selection
- Save/load sub-album setting

### Phase 4: Import Integration - Basic Album
- Build source-album mapping in worker
- Add album addition logic in organize_files()
- Error handling and logging

### Phase 5: Import Integration - Sub-Albums
- Implement sub-album naming derivation
- Implement sub-album storage derivation
- Get-or-create sub-album logic
- Track in SourceDirectorySubAlbums table

---

## Verification Plan

1. **Database upgrade test**: Start app with existing database, verify new columns added
2. **UI test**: Add source, select album, toggle sub-albums, verify persistence after restart
3. **Basic import test**: Import with album selected, verify files in both archive and album
4. **Sub-album test**: Import with sub-albums enabled, verify sub-albums created per subdirectory
5. **Error handling test**: Disconnect album storage mid-import, verify archive completes
6. **Depth test**: Import from deeply nested source, verify all levels create sub-albums

---

## Out of Scope

- Retroactive album assignment (adding existing archive files to albums)
- Album selection dialog during import (pre-configured only)
- Per-file album override (all files from source go to same album)
- Album templates or rules engine
