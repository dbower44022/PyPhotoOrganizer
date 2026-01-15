# UniquePhotos Schema Redesign (v5.0)

**Date:** 2026-01-14
**Author:** Architecture Review
**Status:** Design Phase

## Overview

Complete redesign of file tracking architecture to:
- Store ALL files (originals + versions) in UniquePhotos table
- Eliminate FileHashHistory and FileVersions tables
- Use direct parent-child relationships via `revised_photo` field
- Add source tracking for all files

## New Schema

### UniquePhotos Table (v5.0)

```sql
CREATE TABLE UniquePhotos (
    -- Identity
    file_hash TEXT PRIMARY KEY,              -- SHA-256 hash of THIS file
    partial_hash TEXT,                       -- First N bytes hash for quick comparison
    partial_hash_bytes INTEGER,              -- Bytes used for partial hash (typically 16384)

    -- File Information
    file_size INTEGER NOT NULL,              -- Size in bytes
    file_name TEXT NOT NULL,                 -- Current location (archive or version storage)
    source_path TEXT,                        -- Original import source (NULL for versions)

    -- Revision Tracking (NEW)
    revised_photo TEXT,                      -- Parent file hash (NULL if original import)
    revision_reason TEXT,                    -- 'rotation', 'crop', 'color_adjust', 'exif_edit', etc.
    revision_timestamp TEXT,                 -- When revision was created

    -- Date Information
    create_datetime TEXT,                    -- ISO 8601 timestamp
    create_year TEXT,                        -- YYYY
    create_month TEXT,                       -- MM (zero-padded)
    create_day TEXT,                         -- DD (zero-padded)

    -- Constraints
    FOREIGN KEY (revised_photo) REFERENCES UniquePhotos(file_hash),
    CHECK (revised_photo IS NULL OR revision_reason IS NOT NULL)
);

-- Indexes
CREATE INDEX idx_partial_hash ON UniquePhotos(partial_hash);
CREATE INDEX idx_file_size ON UniquePhotos(file_size);
CREATE INDEX idx_date ON UniquePhotos(create_year, create_month, create_day);
CREATE INDEX idx_file_name ON UniquePhotos(file_name);
CREATE INDEX idx_revised_photo ON UniquePhotos(revised_photo);  -- NEW: For finding children
CREATE INDEX idx_source_path ON UniquePhotos(source_path);      -- NEW: For source lookups
```

### Tables REMOVED

1. **FileHashHistory** - No longer needed, duplicate detection uses UniquePhotos.file_hash directly
2. **FileVersions** - Merged into UniquePhotos via revised_photo/revision_reason fields

### Tables UNCHANGED

- **DatabaseMetadata** - No changes
- **SourceDirectories** - No changes
- **UnreliableDates** - No changes
- **DeletedFiles** - No changes
- **ImportSession** - No changes
- **FileProcessingLog** - No changes
- All other tables unchanged

## Data Model Examples

### Example 1: Original Import

```sql
-- File imported from source
INSERT INTO UniquePhotos (
    file_hash, partial_hash, partial_hash_bytes, file_size,
    file_name, source_path,
    revised_photo, revision_reason, revision_timestamp,
    create_year, create_month, create_day
) VALUES (
    'aaa123...',                                      -- Hash of original file
    'aaa111...',                                      -- Partial hash
    16384,                                            -- Bytes
    2048576,                                          -- 2MB
    '/archive/2024/01/15/vacation_001.jpg',          -- Archive location
    '/mnt/sources/camera/DCIM/IMG_1234.jpg',         -- Source location
    NULL,                                             -- Not a revision
    NULL,                                             -- No revision reason
    NULL,                                             -- No revision timestamp
    '2024', '01', '15'                                -- Date
);
```

### Example 2: File Rotated

```sql
-- Original file moved to version storage when first modified
UPDATE UniquePhotos
SET file_name = '/archive/.pyphotoorg_versions/by_hash/aa/aaa123..._v0.jpg'
WHERE file_hash = 'aaa123...';

-- New rotated file created in archive
INSERT INTO UniquePhotos (
    file_hash, partial_hash, partial_hash_bytes, file_size,
    file_name, source_path,
    revised_photo, revision_reason, revision_timestamp,
    create_year, create_month, create_day
) VALUES (
    'bbb456...',                                      -- NEW hash (rotated bytes)
    'bbb444...',                                      -- NEW partial hash
    16384,
    2150000,                                          -- Slightly larger (rotation expanded)
    '/archive/2024/01/15/vacation_001.jpg',          -- SAME archive location
    '/mnt/sources/camera/DCIM/IMG_1234.jpg',         -- SAME source
    'aaa123...',                                      -- Parent hash
    'rotation',                                       -- Reason
    '2026-01-14T10:30:00',                           -- When rotated
    '2024', '01', '15'                                -- SAME date
);
```

### Example 3: Rotation Chain

```sql
-- Original
file_hash='aaa', revised_photo=NULL, file_name='.../_v0.jpg'

-- Rotated 90°
file_hash='bbb', revised_photo='aaa', revision_reason='rotation', file_name='/archive/2024/01/15/photo.jpg'

-- Cropped
file_hash='ccc', revised_photo='bbb', revision_reason='crop', file_name='/archive/2024/01/15/photo.jpg'

-- Each revision creates a new record, chains via revised_photo
```

### Example 4: EXIF Date Correction

```sql
-- Original file
file_hash='ddd', revised_photo=NULL, file_name='/archive/1000/01/01/scanned.jpg'

-- After EXIF correction and reorganization (hash changes due to EXIF write)
-- Original moved to version storage
UPDATE UniquePhotos SET file_name = '.../_v0.jpg' WHERE file_hash = 'ddd';

-- New version with corrected EXIF
INSERT INTO UniquePhotos (
    file_hash, revised_photo, revision_reason,
    file_name, source_path,
    create_year, create_month, create_day
) VALUES (
    'eee',                                           -- NEW hash (EXIF bytes changed)
    'ddd',                                           -- Parent
    'exif_edit',                                     -- Reason
    '/archive/1995/07/15/scanned.jpg',              -- NEW location (reorganized)
    '/mnt/sources/scanner/IMG_001.jpg',             -- SAME source
    '1995', '07', '15'                               -- CORRECTED date
);
```

## Operations

### 1. Duplicate Detection (During Import)

```python
# find_duplicates() in DuplicateFileDetection.py
def is_duplicate(file_hash):
    cursor.execute("SELECT file_hash FROM UniquePhotos WHERE file_hash = ?", (file_hash,))
    return cursor.fetchone() is not None

# TWO-STAGE HASHING (for large files)
def is_duplicate_two_stage(file_path, file_size):
    if file_size < PARTIAL_HASH_MIN_SIZE:
        # Small files: direct full hash
        full_hash = hash_file(file_path)
        return is_duplicate(full_hash)

    # Large files: check partial hash first
    partial_hash = hash_file_partial(file_path, PARTIAL_HASH_BYTES)

    cursor.execute(
        "SELECT file_hash FROM UniquePhotos WHERE partial_hash = ?",
        (partial_hash,)
    )

    if not cursor.fetchone():
        # No partial match = definitely unique
        return False

    # Partial match found, verify with full hash
    full_hash = hash_file(file_path)
    return is_duplicate(full_hash)
```

**Performance:** O(1) primary key or index lookup

### 2. Initial Import (New File)

```python
def import_file(source_path, archive_path, file_hash, partial_hash, date):
    cursor.execute("""
        INSERT INTO UniquePhotos (
            file_hash, partial_hash, partial_hash_bytes, file_size,
            file_name, source_path,
            revised_photo, revision_reason, revision_timestamp,
            create_year, create_month, create_day
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?)
    """, (
        file_hash, partial_hash, PARTIAL_HASH_BYTES, file_size,
        archive_path, source_path,
        year, month, day
    ))
```

### 3. File Rotation

```python
def rotate_file(old_hash, archive_path, angle):
    # 1. Move original to version storage (if not already there)
    original = get_photo(old_hash)
    if not original['file_name'].startswith('.pyphotoorg_versions'):
        v0_path = get_version_storage_path(old_hash, 0)
        shutil.copy2(original['file_name'], v0_path)

        cursor.execute(
            "UPDATE UniquePhotos SET file_name = ? WHERE file_hash = ?",
            (v0_path, old_hash)
        )

    # 2. Rotate the file
    success, rotated_path, error = ImageModifier.rotate_image(archive_path, angle)

    # 3. Calculate new hash
    new_hash = hash_file(rotated_path)
    new_partial_hash = hash_file_partial(rotated_path, PARTIAL_HASH_BYTES)

    # 4. Insert NEW record for rotated version
    cursor.execute("""
        INSERT INTO UniquePhotos (
            file_hash, partial_hash, partial_hash_bytes, file_size,
            file_name, source_path,
            revised_photo, revision_reason, revision_timestamp,
            create_year, create_month, create_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'rotation', datetime('now'), ?, ?, ?)
    """, (
        new_hash, new_partial_hash, PARTIAL_HASH_BYTES, file_size,
        archive_path,           # SAME archive location (replaces old file)
        original['source_path'], # SAME source
        old_hash,                # Parent hash
        original['create_year'], original['create_month'], original['create_day']
    ))

    # 5. Update UnreliableDates if needed
    cursor.execute(
        "UPDATE UnreliableDates SET file_hash = ? WHERE file_hash = ?",
        (new_hash, old_hash)
    )
```

**Key Point:** Both old_hash (AAA) and new_hash (BBB) exist in UniquePhotos, so both are detected as duplicates on re-import.

### 4. EXIF Date Correction (Changes Hash)

```python
def correct_date_with_exif(old_hash, archive_path, new_year, new_month, new_day):
    # 1. Move original to version storage
    original = get_photo(old_hash)
    v0_path = get_version_storage_path(old_hash, 0)
    shutil.copy2(archive_path, v0_path)

    cursor.execute(
        "UPDATE UniquePhotos SET file_name = ? WHERE file_hash = ?",
        (v0_path, old_hash)
    )

    # 2. Write EXIF to archive file
    write_exif_date(archive_path, new_year, new_month, new_day)

    # 3. Calculate new hash (file changed due to EXIF write)
    new_hash = hash_file(archive_path)
    new_partial_hash = hash_file_partial(archive_path, PARTIAL_HASH_BYTES)

    # 4. Calculate new archive path (reorganized by corrected date)
    new_archive_path = calculate_archive_path(new_year, new_month, new_day, filename)
    shutil.copy2(archive_path, new_archive_path)

    # 5. Insert NEW record for EXIF-corrected version
    cursor.execute("""
        INSERT INTO UniquePhotos (
            file_hash, partial_hash, partial_hash_bytes, file_size,
            file_name, source_path,
            revised_photo, revision_reason, revision_timestamp,
            create_year, create_month, create_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'exif_edit', datetime('now'), ?, ?, ?)
    """, (
        new_hash, new_partial_hash, PARTIAL_HASH_BYTES, file_size,
        new_archive_path,        # NEW location (reorganized)
        original['source_path'], # SAME source
        old_hash,                # Parent hash
        new_year, new_month, new_day  # CORRECTED date
    ))

    # 6. Update UnreliableDates
    cursor.execute(
        "UPDATE UnreliableDates SET file_hash = ?, archive_path = ? WHERE file_hash = ?",
        (new_hash, new_archive_path, old_hash)
    )
```

### 5. Find All Versions of a File

```sql
-- Find all descendants (children, grandchildren, etc.)
WITH RECURSIVE versions AS (
    -- Start with the file we're interested in
    SELECT file_hash, revised_photo, revision_reason, file_name, revision_timestamp
    FROM UniquePhotos
    WHERE file_hash = 'aaa123...'

    UNION ALL

    -- Find all children
    SELECT p.file_hash, p.revised_photo, p.revision_reason, p.file_name, p.revision_timestamp
    FROM UniquePhotos p
    INNER JOIN versions v ON p.revised_photo = v.file_hash
)
SELECT * FROM versions
ORDER BY revision_timestamp;
```

**Result:**
```
file_hash    | revised_photo | revision_reason | file_name
-------------|---------------|-----------------|------------------
aaa123...    | NULL          | NULL            | .../_v0.jpg
bbb456...    | aaa123...     | rotation        | /archive/.../photo.jpg
ccc789...    | bbb456...     | crop            | /archive/.../photo.jpg
```

### 6. Find Original File (Walk Up Chain)

```sql
-- Walk up the chain to find the original
WITH RECURSIVE ancestors AS (
    -- Start with current file
    SELECT file_hash, revised_photo, revision_reason
    FROM UniquePhotos
    WHERE file_hash = 'ccc789...'

    UNION ALL

    -- Walk up to parents
    SELECT p.file_hash, p.revised_photo, p.revision_reason
    FROM UniquePhotos p
    INNER JOIN ancestors a ON p.file_hash = a.revised_photo
)
SELECT * FROM ancestors
WHERE revised_photo IS NULL;  -- Original has no parent
```

### 7. Delete File to Vault

```python
def delete_to_vault(file_hash):
    # 1. Copy to vault
    photo = get_photo(file_hash)
    vault_path = calculate_vault_path(photo['file_name'])
    shutil.copy2(photo['file_name'], vault_path)

    # 2. Remove from UnreliableDates (if present)
    cursor.execute("DELETE FROM UnreliableDates WHERE file_hash = ?", (file_hash,))

    # 3. Record in DeletedFiles
    cursor.execute("""
        INSERT INTO DeletedFiles (file_hash, original_archive_path, delete_vault_path, ...)
        VALUES (?, ?, ?, ...)
    """, (file_hash, photo['file_name'], vault_path, ...))

    # 4. Delete archive file
    os.remove(photo['file_name'])

    # 5. UPDATE UniquePhotos (keep record, update location)
    cursor.execute(
        "UPDATE UniquePhotos SET file_name = ? WHERE file_hash = ?",
        (vault_path, file_hash)
    )

    # NOTE: We KEEP the UniquePhotos record so it's still detected as duplicate!
    # The file_name just points to vault instead of archive
```

**Important:** We don't delete from UniquePhotos - the record stays for duplicate detection.

### 8. Restore File from Vault

```python
def restore_from_vault(file_hash):
    # 1. Get deleted file info
    deleted = get_deleted_file(file_hash)
    vault_path = deleted['delete_vault_path']

    # 2. Calculate restore path
    restore_path = deleted['original_archive_path']
    if os.path.exists(restore_path):
        restore_path = get_unique_filename(restore_path)

    # 3. Copy from vault to archive
    shutil.copy2(vault_path, restore_path)

    # 4. Update UniquePhotos location
    cursor.execute(
        "UPDATE UniquePhotos SET file_name = ? WHERE file_hash = ?",
        (restore_path, file_hash)
    )

    # 5. Mark as restored in DeletedFiles
    cursor.execute(
        "UPDATE DeletedFiles SET is_restored = 1, restore_timestamp = datetime('now') WHERE file_hash = ?",
        (file_hash,)
    )

    # 6. Delete from vault
    os.remove(vault_path)
```

## Migration Strategy

**NOTE:** Per user request, we will NOT migrate existing databases. Users will start fresh imports.

### New Database Creation

```python
# migrations/schema_v5.py
def create_schema_v5(conn):
    """Create clean v5 schema for new databases."""

    # UniquePhotos with new fields
    conn.execute("""
        CREATE TABLE UniquePhotos (
            file_hash TEXT PRIMARY KEY,
            partial_hash TEXT,
            partial_hash_bytes INTEGER,
            file_size INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            source_path TEXT,
            revised_photo TEXT,
            revision_reason TEXT,
            revision_timestamp TEXT,
            create_datetime TEXT,
            create_year TEXT,
            create_month TEXT,
            create_day TEXT,
            FOREIGN KEY (revised_photo) REFERENCES UniquePhotos(file_hash),
            CHECK (revised_photo IS NULL OR revision_reason IS NOT NULL)
        )
    """)

    # Indexes
    conn.execute("CREATE INDEX idx_partial_hash ON UniquePhotos(partial_hash)")
    conn.execute("CREATE INDEX idx_file_size ON UniquePhotos(file_size)")
    conn.execute("CREATE INDEX idx_date ON UniquePhotos(create_year, create_month, create_day)")
    conn.execute("CREATE INDEX idx_file_name ON UniquePhotos(file_name)")
    conn.execute("CREATE INDEX idx_revised_photo ON UniquePhotos(revised_photo)")
    conn.execute("CREATE INDEX idx_source_path ON UniquePhotos(source_path)")

    # All other tables unchanged
    create_database_metadata_table(conn)
    create_source_directories_table(conn)
    create_unreliable_dates_table(conn)
    create_deleted_files_table(conn)
    create_import_session_table(conn)
    # ... etc

    # DO NOT create: FileHashHistory, FileVersions

    # Set schema version to 5
    conn.execute("UPDATE DatabaseMetadata SET schema_version = 5")
```

## Code Changes Required

### 1. DuplicateFileDetection.py

**Remove:**
- `add_hash_to_history()` method
- `add_version_hash_to_history()` method
- `get_all_historical_hashes()` method
- `get_photo_by_historical_hash()` method

**Modify:**
- `insert_unique_photo()` - Add source_path parameter
- `find_duplicates()` - Remove FileHashHistory references
- Duplicate detection - Direct UniquePhotos.file_hash lookup only

### 2. rotate_worker.py

**Changes:**
- Move original to version storage (update UniquePhotos.file_name)
- INSERT new record for rotated file (with revised_photo, revision_reason)
- Update UnreliableDates.file_hash to new hash
- Remove all FileHashHistory and FileVersions code

### 3. delete_worker.py

**Changes:**
- Update UniquePhotos.file_name to vault path (don't DELETE record)
- Continue removing from UnreliableDates

### 4. restore_worker.py

**Changes:**
- Update UniquePhotos.file_name to restored path
- Remove any FileHashHistory code

### 5. date_correction_dialog.py / exif_writer.py

**Changes:**
- Move original to version storage
- INSERT new record for EXIF-corrected file
- Update UnreliableDates.file_hash
- Remove all FileHashHistory code

### 6. database_metadata.py

**Changes:**
- Remove `sync_versions_to_hash_history()` method
- Update schema version constant to 5

### 7. image_modifier.py / VersionManager

**Decision:** Keep or remove VersionManager class?

**Option A:** Remove VersionManager, handle versions directly in workers
- Simpler, less abstraction
- Workers directly INSERT into UniquePhotos

**Option B:** Keep VersionManager, adapt to new schema
- Maintains abstraction
- VersionManager.create_new_version() → INSERT into UniquePhotos

**Recommendation:** Remove VersionManager, use direct SQL in workers (simpler).

### 8. main.py

**Changes:**
- Pass source_path to insert_unique_photo()
- Remove any FileHashHistory references

## Benefits Summary

### Performance
- ✅ Duplicate detection: Simple primary key lookup (same speed)
- ✅ Partial hash optimization: Still works (indexed)
- ✅ No recursive queries in hot path

### Simplicity
- ✅ Single source of truth (UniquePhotos)
- ✅ No table synchronization needed
- ✅ Fewer database tables (remove 2 tables)
- ✅ Less code to maintain

### Functionality
- ✅ Complete version history (via revised_photo chain)
- ✅ Source tracking (source_path field)
- ✅ Partial hashes for versions (calculated on rotation)
- ✅ Clear parent-child relationships

### Data Integrity
- ✅ Original files preserved (in version storage)
- ✅ All versions tracked (separate records)
- ✅ Foreign key constraints (revised_photo → file_hash)
- ✅ Check constraint (revised_photo requires revision_reason)

## Testing Plan

### 1. Duplicate Detection
- Import file with hash AAA
- Verify UniquePhotos contains AAA
- Try to re-import same file
- Verify detected as duplicate

### 2. Rotation
- Import file (hash AAA)
- Rotate file (creates hash BBB)
- Verify UniquePhotos contains both AAA and BBB
- Verify BBB.revised_photo = AAA
- Verify BBB.revision_reason = 'rotation'
- Try to re-import original → detected as duplicate
- Try to re-import rotated → detected as duplicate

### 3. Rotation Chain
- Import file (AAA)
- Rotate 90° (BBB)
- Crop (CCC)
- Verify chain: AAA ← BBB ← CCC
- Verify all three detected as duplicates

### 4. EXIF Correction
- Import file with wrong date (hash DDD)
- Correct date with EXIF write (hash changes to EEE)
- Verify both DDD and EEE in UniquePhotos
- Verify EEE.revised_photo = DDD
- Verify EEE.revision_reason = 'exif_edit'

### 5. Delete to Vault
- Delete file to vault
- Verify UniquePhotos.file_name updated to vault path
- Verify record NOT deleted from UniquePhotos
- Try to re-import → still detected as duplicate

### 6. Partial Hash Optimization
- Import large file (>1MB)
- Verify partial_hash stored
- Import another large file with same start
- Verify partial hash checked first
- Verify full hash calculated for collision

## Questions for Review

1. ✅ **Source path for versions**: Should rotated files keep the original source_path? (YES - done in design)

2. ✅ **Deletion behavior**: Keep UniquePhotos record with vault path? (YES - for duplicate detection)

3. **Version storage path**: Should we update file_name when moving to version storage?
   - Current design: YES - file_name always reflects current location
   - Alternative: Add separate field for current_location vs original_archive_location

4. **Partial hash for versions**: Should we calculate partial_hash for rotated files?
   - Current design: YES - maintains consistency
   - Cost: Extra hashing time during rotation
   - Benefit: Two-stage detection works for versions too

5. **Recursive queries**: Do we need to optimize recursive CTEs?
   - Only used for UI display (version history)
   - NOT used in import hot path
   - Current design: Acceptable, queries are infrequent

## Implementation Order

1. **Schema changes** (create v5 migration)
2. **DuplicateFileDetection.py** (core duplicate detection)
3. **main.py** (import process)
4. **rotate_worker.py** (rotation)
5. **exif_writer.py + date_correction_dialog.py** (EXIF edits)
6. **delete_worker.py + restore_worker.py** (deletion/restore)
7. **Remove obsolete code** (FileHashHistory, FileVersions, VersionManager)
8. **Testing** (full regression suite)

---

**Status:** Ready for implementation
**Next Step:** Create migration script schema_v5.py
