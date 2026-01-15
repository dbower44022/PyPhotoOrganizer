# Schema v5 Implementation Summary

## Overview

Schema v5 implements a unified UniquePhotos table design that eliminates the redundant FileHashHistory and FileVersions tables. This provides a cleaner architecture with simpler duplicate detection and revision tracking.

## Files Modified

### 1. migrations/schema_v5.py (NEW)
**Created**: Complete migration script for v4 → v5

**What it does:**
- Drops obsolete tables: FileHashHistory, FileVersions, ModificationSession, ModificationLog
- Recreates UniquePhotos table with new columns:
  - `source_path` - Original import source location
  - `revised_photo` - Parent file hash (chain topology)
  - `revision_reason` - Why revision was created ('rotation', 'crop', 'exif_edit', etc.)
  - `revision_timestamp` - When revision was created
- Clears UnreliableDates and DeletedFiles tables (reference old hashes)
- Resets total_photos counter to 0
- Creates 5 indexes for performance

**Safety features:**
- Checks current schema version
- Requires user confirmation (interactive mode)
- Updates schema_version to 5
- Comprehensive logging

**Usage:**
```bash
python migrations/schema_v5.py <database_path>
```

### 2. DuplicateFileDetection.py
**Modified**: PhotoDatabase class methods

**Changes:**

#### `initialize_database()` (lines 109-183)
- Removed FileHashHistory table creation
- Updated UniquePhotos schema with v5 columns
- Added 5 new indexes (revised, source, year, date composite)
- Simplified comments to reflect new design

#### `insert_unique_photo()` (lines 201-238)
- Added `source_path` parameter (optional)
- Removed FileHashHistory insert
- Sets `revised_photo=NULL, revision_reason=NULL` for original imports
- Simplified logging

#### Removed methods (obsolete in v5):
- `is_duplicate_hash_in_history()` - No longer needed (primary key lookup)
- `get_all_historical_hashes()` - No longer needed
- `add_hash_to_history()` - Replaced by create_revision()
- `add_version_hash_to_history()` - Replaced by create_revision()
- `get_photo_by_historical_hash()` - No longer needed

#### New methods (added for v5):

**`create_revision()`** (lines 299-345)
- Insert new revision record into UniquePhotos
- Links to parent via `revised_photo` field
- Used for rotations, crops, EXIF edits, etc.
- Calculates partial hash for large files
- Returns bool success/failure

**`get_revision_chain()`** (lines 347-400)
- Walk revision chain from file back to original
- Returns list ordered from original to current
- Prevents infinite loops with max_depth=50
- Useful for viewing version history

**`get_all_revisions_of()`** (lines 402-438)
- Find all direct revisions (children) of a file
- Returns list ordered by revision_timestamp
- Useful for showing "what was created from this file"

**Duplicate Detection (v5):**
- Simple primary key lookup: `SELECT file_hash FROM UniquePhotos WHERE file_hash = ?`
- O(1) performance via indexed hash
- Works for ALL files (originals + revisions) automatically

### 3. DuplicateFileDetection.py - find_duplicates() (line 1757)
**Modified**: Pass source_path parameter

**Change:**
```python
db.insert_unique_photo(
    file_hash, filename, create_datetime, year, month, day,
    partial_hash=partial_hash,
    partial_hash_bytes=partial_hash_bytes,
    file_size=file_size,
    source_path=filename  # Original source location (v5 schema)
)
```

### 4. ui/reprocess_worker.py (line 249)
**Modified**: Pass source_path parameter

**Change:**
```python
db.insert_unique_photo(
    file_hash=file_hash,
    file_path=target_path,
    create_datetime=create_datetime,
    create_year=year,
    create_month=month,
    create_day=day,
    partial_hash=partial_hash,
    partial_hash_bytes=partial_hash_bytes,
    file_size=file_size,
    source_path=source_path  # Preserve original import source (v5 schema)
)
```

### 5. ui/rotate_worker.py (lines 47-247)
**Modified**: Use create_revision() instead of VersionManager

**Major changes:**
- Removed VersionManager initialization
- Removed v0 version saving logic
- Simplified to in-place rotation
- Use create_revision() to insert new record
- Update UnreliableDates with new hash
- Removed FileHashHistory usage

**New workflow:**
1. Get original file metadata from UniquePhotos
2. Rotate image (creates temp file)
3. Replace archive file with rotated version (copy-verify-delete pattern)
4. Calculate new hash and partial hash
5. Create revision record with `revised_photo=original_hash`
6. Update UnreliableDates table with new hash
7. Log to audit trail

**Preserved safety features:**
- Source file protection check (lines 102-113)
- Backup-restore pattern for file replacement
- Permission error handling (copy2 → copy fallback)
- Size verification after replacement

## Architecture Changes

### Old Design (v4):
```
UniquePhotos table (current file state)
  ↓
FileHashHistory table (all historical hashes)
  ↓
FileVersions table (version metadata)
```

**Duplicate Detection:**
```sql
-- Check UniquePhotos
SELECT file_hash FROM UniquePhotos WHERE file_hash = ?
-- If not found, check FileHashHistory
SELECT current_file_hash FROM FileHashHistory WHERE historical_hash = ?
```

### New Design (v5):
```
UniquePhotos table (ALL files: originals + revisions)
  ├─ original import (revised_photo=NULL)
  ├─ revision 1 (revised_photo=original_hash)
  ├─ revision 2 (revised_photo=revision_1_hash)
  └─ ... (chain topology)
```

**Duplicate Detection:**
```sql
-- Single primary key lookup
SELECT file_hash FROM UniquePhotos WHERE file_hash = ?
```

## Benefits of v5

1. **Simpler Duplicate Detection**
   - Single table lookup instead of 2-table join
   - O(1) primary key lookup performance
   - No complex hash history management

2. **Cleaner Data Model**
   - Single source of truth (UniquePhotos)
   - No redundant tables
   - Easier to understand and maintain

3. **Better Revision Tracking**
   - `revised_photo` chain shows parent-child relationships
   - `revision_reason` documents why each revision was created
   - `source_path` preserves original import location
   - `revision_timestamp` shows when each revision was made

4. **Reduced Database Complexity**
   - 4 fewer tables to maintain
   - Fewer indexes to update on inserts
   - Simpler backup/restore operations

5. **Performance**
   - Faster duplicate detection (one lookup vs two)
   - Fewer database writes per operation
   - Better index utilization

## Migration Notes

### What is Preserved:
- DatabaseMetadata (database config, archive location, settings)
- SourceDirectories (persistent source folder configurations)
- ImportSession, FileProcessingLog, DuplicateMapping, AuditRetentionSettings (audit history)
- DeletedFiles structure (will be repopulated on fresh import)
- UnreliableDates structure (will be repopulated on fresh import)

### What is Lost:
- All UniquePhotos records (MUST re-import photos)
- All FileHashHistory records (no longer needed)
- All FileVersions records (merged into UniquePhotos)
- All ModificationSession/ModificationLog records (no longer used)
- UnreliableDates and DeletedFiles data (tables cleared, will repopulate)

### Re-Import Required:
Yes, this is a **breaking change** requiring fresh photo imports. The migration:
1. Preserves database configuration and settings
2. Preserves audit history (for analysis)
3. Clears all file records
4. User must re-run import through Setup tab

### Migration Workflow:
1. Backup database before migration
2. Run migration script: `python migrations/schema_v5.py PhotoDB.db`
3. Confirm migration when prompted
4. Re-import photos through GUI Setup tab
5. Photos will be detected as duplicates (skip re-copy)
6. Database will repopulate with v5 schema

## Testing Checklist

- [ ] Migration script runs successfully
- [ ] UniquePhotos table created with v5 schema
- [ ] Obsolete tables removed
- [ ] Import process works with source_path tracking
- [ ] Duplicate detection works (finds existing files)
- [ ] Rotation creates revision records correctly
- [ ] Revision chain queries work
- [ ] UnreliableDates updates with new hashes after rotation
- [ ] Thumbnail cache invalidates correctly
- [ ] Delete and restore operations still work
- [ ] Audit logging continues to function

## Known Limitations

1. **No Migration from v4 Data:**
   - Cannot automatically convert FileHashHistory → UniquePhotos revisions
   - Cannot preserve FileVersions version history
   - Requires fresh import

2. **Rotation Workflow Changed:**
   - No longer saves v0 version to separate storage
   - In-place replacement only
   - Cannot "undo" rotation back to original
   - Future enhancement: Add undo capability via revision chain

3. **EXIF Editing Not Yet Updated:**
   - date_correction_dialog.py still uses old approach
   - exif_writer.py needs updating for v5
   - Will be addressed in next phase

## Next Steps

1. Update delete_worker.py for v5 (if needed)
2. Update restore_worker.py for v5 (if needed)
3. Update exif_writer.py and date_correction_dialog.py for v5
4. Remove obsolete VersionManager class from image_modifier.py
5. Update tests to use v5 schema
6. Update API.md and ARCHITECTURE.md documentation

## Status

**Implementation Status:** COMPLETE (Phase 1)
- ✅ Migration script created
- ✅ DuplicateFileDetection.py updated
- ✅ insert_unique_photo() calls updated
- ✅ rotate_worker.py updated
- ⏳ delete_worker.py (needs review)
- ⏳ restore_worker.py (needs review)
- ⏳ EXIF editing (next phase)
- ⏳ Testing and validation

**Ready for:** Migration testing with user's database
